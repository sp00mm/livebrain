import io
import struct
import threading
import time
import wave
from datetime import datetime
from unittest.mock import MagicMock, patch

from models import SpeakerType
from services.whisper_service import WhisperTranscriptionService


def _make_wav(num_samples=48000, sample_rate=48000):
    """Create a WAV file with the given number of samples at the given rate."""
    samples = [0] * num_samples
    pcm = struct.pack(f'{num_samples}h', *samples)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _make_segment(start, end, text):
    seg = MagicMock()
    seg.start = start
    seg.end = end
    seg.text = text
    return seg


class TestWhisperTranscriptionService:
    def test_basic_transcription(self, tmp_path):
        wav_data = _make_wav(48000)
        mic_path = tmp_path / 'mic.wav'
        system_path = tmp_path / 'system.wav'
        mic_path.write_bytes(wav_data)
        system_path.write_bytes(wav_data)

        service = WhisperTranscriptionService()

        mock_response = MagicMock()
        mock_response.segments = [
            _make_segment(0.0, 0.5, ' Hello'),
            _make_segment(0.5, 1.0, ' World'),
        ]

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        service._client = mock_client

        start_time = datetime(2026, 1, 1)
        entries = service.transcribe_session('session-1', str(mic_path), str(system_path), start_time)

        assert len(entries) == 4
        user_entries = [e for e in entries if e.speaker == SpeakerType.USER]
        other_entries = [e for e in entries if e.speaker == SpeakerType.OTHER]
        assert len(user_entries) == 2
        assert len(other_entries) == 2
        assert user_entries[0].text == ' Hello'
        assert all(e.session_id == 'session-1' for e in entries)
        assert entries == sorted(entries, key=lambda e: e.timestamp)

    def test_incremental_transcription(self, tmp_path):
        wav_data_1 = _make_wav(48000)
        mic_path = tmp_path / 'mic.wav'
        system_path = tmp_path / 'system.wav'
        mic_path.write_bytes(wav_data_1)
        system_path.write_bytes(wav_data_1)

        service = WhisperTranscriptionService()

        mock_response = MagicMock()
        mock_response.segments = [_make_segment(0.0, 0.5, ' First')]

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response
        service._client = mock_client

        start_time = datetime(2026, 1, 1)
        service.transcribe_session('s1', str(mic_path), str(system_path), start_time)

        state_key = ('s1', 'mic')
        assert service._states[state_key].last_frame == 48000

        wav_data_2 = _make_wav(96000)
        mic_path.write_bytes(wav_data_2)
        system_path.write_bytes(wav_data_2)

        mock_response_2 = MagicMock()
        mock_response_2.segments = [_make_segment(0.0, 0.5, ' Second')]
        mock_client.audio.transcriptions.create.return_value = mock_response_2

        service.transcribe_session('s1', str(mic_path), str(system_path), start_time)

        overlap_frames = service.OVERLAP_SECONDS * service.SAMPLE_RATE
        expected_start = max(0, 48000 - overlap_frames)
        assert expected_start == 0  # 48000 < 20*48000, so start from 0

        assert service._states[state_key].last_frame == 96000

    def test_downsampling(self, tmp_path):
        num_samples = 48000 * 3
        wav_data = _make_wav(num_samples)
        mic_path = tmp_path / 'mic.wav'
        system_path = tmp_path / 'system.wav'
        mic_path.write_bytes(wav_data)
        system_path.write_bytes(_make_wav(0))

        service = WhisperTranscriptionService()

        captured_files = []

        def capture_create(**kwargs):
            file_arg = kwargs['file']
            file_bytes = file_arg[1].read()
            file_arg[1].seek(0)
            with wave.open(io.BytesIO(file_bytes), 'rb') as wf:
                captured_files.append({
                    'nframes': wf.getnframes(),
                    'framerate': wf.getframerate(),
                })
            resp = MagicMock()
            resp.segments = []
            return resp

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = capture_create
        service._client = mock_client

        start_time = datetime(2026, 1, 1)
        service.transcribe_session('s1', str(mic_path), str(system_path), start_time)

        assert len(captured_files) >= 1
        assert captured_files[0]['framerate'] == 16000
        assert captured_files[0]['nframes'] == num_samples // 3

    def test_concurrent_locking(self, tmp_path):
        wav_data = _make_wav(48000)
        mic_path = tmp_path / 'mic.wav'
        system_path = tmp_path / 'system.wav'
        mic_path.write_bytes(wav_data)
        system_path.write_bytes(wav_data)

        service = WhisperTranscriptionService()

        call_times = []
        original_lock = service._lock

        def slow_create(**kwargs):
            call_times.append(time.time())
            time.sleep(0.1)
            resp = MagicMock()
            resp.segments = []
            return resp

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = slow_create
        service._client = mock_client

        start_time = datetime(2026, 1, 1)
        threads = []
        for i in range(2):
            t = threading.Thread(
                target=service.transcribe_session,
                args=(f's{i}', str(mic_path), str(system_path), start_time)
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(call_times) >= 2
        # Second set of calls should start after first set finishes
        # Each session makes 2 calls (mic + system), so calls 2+ should be after call 0 + 0.1s
        assert call_times[-1] - call_times[0] >= 0.1

    def test_empty_audio(self, tmp_path):
        wav_data = _make_wav(0)
        mic_path = tmp_path / 'mic.wav'
        system_path = tmp_path / 'system.wav'
        mic_path.write_bytes(wav_data)
        system_path.write_bytes(wav_data)

        service = WhisperTranscriptionService()
        mock_client = MagicMock()
        service._client = mock_client

        start_time = datetime(2026, 1, 1)
        entries = service.transcribe_session('s1', str(mic_path), str(system_path), start_time)

        assert entries == []
        mock_client.audio.transcriptions.create.assert_not_called()
