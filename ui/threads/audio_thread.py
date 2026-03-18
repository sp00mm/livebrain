import struct
from collections import deque

from PySide6.QtCore import QThread, Signal

from audio.storage import AudioStorage
from audio.capture import create_mic_capture, create_system_capture
from audio.transcription import create_transcriber, create_subprocess_transcriber
from models import SpeakerType


class AudioThread(QThread):
    transcript_update = Signal(str, str, float, bool)
    audio_level = Signal(float, float)
    status_changed = Signal(str)
    error = Signal(str)

    SAMPLE_RATE_KHZ = 48
    CHUNK_MS = 10
    DECAY_CHUNKS = 3
    HISTORY_SIZE = 10
    MIC_RATIO_THRESHOLD = 3.0

    def __init__(self, session_id: str, input_device=None, output_device=None):
        super().__init__()
        self.session_id = session_id
        self._stop_requested = False
        self._system_energy = deque(maxlen=self.HISTORY_SIZE)
        self._chunks_since_active = self.DECAY_CHUNKS + 1
        self._latest_mic_rms = 0.0
        self._latest_system_rms = 0.0
        self._transcribers_active = True

        self._storage = AudioStorage(session_id)
        self._mic_capture = create_mic_capture(device=input_device)
        self._mic_transcriber = create_transcriber()
        self._system_capture = create_system_capture(device=output_device)
        self._system_transcriber = create_subprocess_transcriber()

    def run(self):
        self._stop_requested = False
        self.status_changed.emit('Starting')

        self._storage.start()

        self._mic_capture.on_audio = self._on_mic_audio
        self._mic_capture.start()
        self._system_capture.on_audio = self._on_system_audio
        self._system_capture.start()

        self.msleep(100)

        self._mic_transcriber.start(
            lambda text, conf, final: self._on_transcript(SpeakerType.USER, text, conf, final)
        )
        self._system_transcriber.start(
            lambda text, conf, final: self._on_transcript(SpeakerType.OTHER, text, conf, final)
        )

        self.status_changed.emit('Recording')

        while not self._stop_requested:
            self.audio_level.emit(self._latest_mic_rms, self._latest_system_rms)
            self.msleep(100)

        self._mic_capture.stop()
        self._system_capture.stop()
        if self._transcribers_active:
            self._mic_transcriber.stop()
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
        self._latest_mic_rms = mic_rms

        if not self._transcribers_active:
            return

        system_avg = sum(self._system_energy) / len(self._system_energy) if self._system_energy else 0

        if self._chunks_since_active > self.DECAY_CHUNKS:
            self._mic_transcriber.feed_audio(audio_data)
        elif system_avg > 0 and mic_rms / system_avg > self.MIC_RATIO_THRESHOLD:
            self._mic_transcriber.feed_audio(audio_data)

    def _on_system_audio(self, audio_data: bytes, _timestamp: float):
        int16_data = AudioStorage.convert_float32_to_int16(audio_data)
        self._storage.write_system(int16_data)
        if self._transcribers_active:
            self._system_transcriber.feed_audio(audio_data)

        floats = struct.unpack(f'{len(audio_data) // 4}f', audio_data)
        self._latest_system_rms = (sum(f * f for f in floats) / len(floats)) ** 0.5

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

    def stop_transcribers(self):
        self._mic_transcriber.stop()
        self._system_transcriber.stop()
        self._transcribers_active = False

    def start_transcribers(self):
        self._mic_transcriber = create_transcriber()
        self._system_transcriber = create_subprocess_transcriber()
        self._mic_transcriber.start(
            lambda text, conf, final: self._on_transcript(SpeakerType.USER, text, conf, final)
        )
        self._system_transcriber.start(
            lambda text, conf, final: self._on_transcript(SpeakerType.OTHER, text, conf, final)
        )
        self._transcribers_active = True

    def _on_transcript(self, speaker: SpeakerType, text: str, confidence: float, is_final: bool):
        self.transcript_update.emit(speaker.value, text, confidence, is_final)
