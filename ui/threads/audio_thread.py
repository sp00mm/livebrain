from PySide6.QtCore import QThread, Signal

from audio.storage import AudioStorage
from audio.capture.macos import MacOSMicCapture, MacOSSystemCapture
from audio.transcription import AppleSpeechTranscriber, SubprocessTranscriber
from models import SpeakerType


class AudioThread(QThread):
    transcript_update = Signal(str, str, float, bool)  # speaker, text, confidence, is_final
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self._stop_requested = False

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
        self._mic_transcriber.feed_audio(audio_data)

    def _on_system_audio(self, audio_data: bytes, _timestamp: float):
        int16_data = AudioStorage.convert_float32_to_int16(audio_data)
        self._storage.write_system(int16_data)
        self._system_transcriber.feed_audio(audio_data)

    def _on_transcript(self, speaker: SpeakerType, text: str, confidence: float, is_final: bool):
        self.transcript_update.emit(speaker.value, text, confidence, is_final)
