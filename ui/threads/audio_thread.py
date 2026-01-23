import struct
from collections import deque

from PySide6.QtCore import QThread, Signal

from audio.storage import AudioStorage
from audio.capture.macos import MacOSMicCapture, MacOSSystemCapture
from audio.transcription import AppleSpeechTranscriber, SubprocessTranscriber
from models import SpeakerType


class AudioThread(QThread):
    transcript_update = Signal(str, str, float, bool)  # speaker, text, confidence, is_final
    status_changed = Signal(str)
    error = Signal(str)

    SAMPLE_RATE_KHZ = 48
    CHUNK_MS = 10
    DECAY_CHUNKS = 3
    HISTORY_SIZE = 10
    MIC_RATIO_THRESHOLD = 3.0

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self._stop_requested = False
        self._system_energy = deque(maxlen=self.HISTORY_SIZE)
        self._chunks_since_active = self.DECAY_CHUNKS + 1

        self._storage = AudioStorage(session_id)
        self._mic_capture = MacOSMicCapture()
        self._mic_transcriber = AppleSpeechTranscriber()
        self._system_capture = MacOSSystemCapture()
        self._system_transcriber = SubprocessTranscriber()

    def run(self):
        self._stop_requested = False
        self.status_changed.emit('Starting')

        self._storage.start()

        # Start both captures first
        self._mic_capture.on_audio = self._on_mic_audio
        self._mic_capture.start()
        self._system_capture.on_audio = self._on_system_audio
        self._system_capture.start()

        # Small delay to let audio start flowing
        self.msleep(100)

        # Then start transcribers
        self._mic_transcriber.start(
            lambda text, conf, final: self._on_transcript(SpeakerType.USER, text, conf, final)
        )
        self._system_transcriber.start(
            lambda text, conf, final: self._on_transcript(SpeakerType.OTHER, text, conf, final)
        )

        self.status_changed.emit('Recording')

        while not self._stop_requested:
            self.msleep(100)

        self._mic_capture.stop()
        self._mic_transcriber.stop()
        self._system_capture.stop()
        self._system_transcriber.stop()
        self._storage.stop()

        self.status_changed.emit('Stopped')

    def stop_recording(self):
        self._stop_requested = True

    def _on_mic_audio(self, audio_data: bytes, _timestamp: float):
        int16_data = AudioStorage.convert_float32_to_int16(audio_data)
        self._storage.write_mic(int16_data)

        floats = struct.unpack(f'{len(audio_data) // 4}f', audio_data)
        mic_rms = (sum(f * f for f in floats) / len(floats)) ** 0.5

        system_avg = sum(self._system_energy) / len(self._system_energy) if self._system_energy else 0

        if self._chunks_since_active > self.DECAY_CHUNKS:
            self._mic_transcriber.feed_audio(audio_data)
        elif system_avg > 0 and mic_rms / system_avg > self.MIC_RATIO_THRESHOLD:
            self._mic_transcriber.feed_audio(audio_data)

    def _on_system_audio(self, audio_data: bytes, _timestamp: float):
        int16_data = AudioStorage.convert_float32_to_int16(audio_data)
        self._storage.write_system(int16_data)
        self._system_transcriber.feed_audio(audio_data)

        floats = struct.unpack(f'{len(audio_data) // 4}f', audio_data)
        samples_per_chunk = self.CHUNK_MS * self.SAMPLE_RATE_KHZ

        for i in range(0, len(floats), samples_per_chunk):
            chunk = floats[i:i + samples_per_chunk]
            rms = (sum(f * f for f in chunk) / len(chunk)) ** 0.5
            self._system_energy.append(rms)

            avg = sum(self._system_energy) / len(self._system_energy)
            threshold = max(0.01, avg * 1.5)

            if rms > threshold:
                self._chunks_since_active = 0
            else:
                self._chunks_since_active += 1

    def _on_transcript(self, speaker: SpeakerType, text: str, confidence: float, is_final: bool):
        self.transcript_update.emit(speaker.value, text, confidence, is_final)
