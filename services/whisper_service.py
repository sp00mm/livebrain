import io
import struct
import threading
import wave
from dataclasses import dataclass
from datetime import datetime, timedelta

from openai import OpenAI

from models import TranscriptEntry, SpeakerType


@dataclass
class _SourceState:
    last_frame: int = 0


class WhisperTranscriptionService:
    SAMPLE_RATE = 48000
    TARGET_RATE = 16000
    OVERLAP_SECONDS = 20
    MAX_CHUNK_BYTES = 24 * 1024 * 1024

    def __init__(self):
        self._client = None
        self._lock = threading.Lock()
        self._states: dict[tuple[str, str], _SourceState] = {}

    def _get_client(self) -> OpenAI:
        if not self._client:
            from services.secrets import secrets
            self._client = OpenAI(api_key=secrets.get('openai_api_key'))
        return self._client

    def transcribe_session(self, session_id: str, mic_path: str, system_path: str,
                           session_start_time: datetime) -> list[TranscriptEntry]:
        with self._lock:
            mic_entries = self._transcribe_source(session_id, mic_path, 'mic',
                                                  SpeakerType.USER, session_start_time)
            system_entries = self._transcribe_source(session_id, system_path, 'system',
                                                     SpeakerType.OTHER, session_start_time)
            combined = mic_entries + system_entries
            combined.sort(key=lambda e: e.timestamp)
            return combined

    def _transcribe_source(self, session_id: str, wav_path: str, source_name: str,
                           speaker_type: SpeakerType, session_start_time: datetime) -> list[TranscriptEntry]:
        key = (session_id, source_name)
        state = self._states.setdefault(key, _SourceState())

        with open(wav_path, 'rb') as f:
            f.seek(44)
            raw_bytes = f.read()

        total_frames = len(raw_bytes) // 2
        overlap_frames = self.OVERLAP_SECONDS * self.SAMPLE_RATE
        start_frame = max(0, state.last_frame - overlap_frames)

        new_data = raw_bytes[start_frame * 2:]
        if not new_data:
            return []

        samples = struct.unpack(f'{len(new_data) // 2}h', new_data)
        downsampled = samples[::3]
        resampled_bytes = struct.pack(f'{len(downsampled)}h', *downsampled)

        chunks = self._chunk_audio(resampled_bytes)
        entries = []
        chunk_offset = 0.0

        for chunk_bytes in chunks:
            wav_buffer = self._build_wav(chunk_bytes)
            response = self._get_client().audio.transcriptions.create(
                model='whisper-1',
                file=('audio.wav', wav_buffer),
                response_format='verbose_json',
                timestamp_granularities=['segment']
            )

            for segment in response.segments:
                absolute_seconds = segment.start + chunk_offset + (start_frame / self.SAMPLE_RATE)

                if start_frame > 0 and absolute_seconds < (state.last_frame / self.SAMPLE_RATE) - 2:
                    continue

                entries.append(TranscriptEntry(
                    session_id=session_id,
                    speaker=speaker_type,
                    text=segment.text,
                    confidence=1.0,
                    timestamp=session_start_time + timedelta(seconds=absolute_seconds)
                ))

            chunk_sample_count = len(chunk_bytes) // 2
            chunk_offset += chunk_sample_count / self.TARGET_RATE

        state.last_frame = total_frames
        return entries

    def _chunk_audio(self, audio_bytes: bytes) -> list[bytes]:
        return [audio_bytes[i:i + self.MAX_CHUNK_BYTES]
                for i in range(0, len(audio_bytes), self.MAX_CHUNK_BYTES)]

    def _build_wav(self, pcm_bytes: bytes) -> io.BytesIO:
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.TARGET_RATE)
            wf.writeframes(pcm_bytes)
        buf.seek(0)
        return buf
