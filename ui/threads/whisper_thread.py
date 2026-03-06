from PySide6.QtCore import QThread, Signal


class WhisperTranscriptionThread(QThread):
    status_changed = Signal(str)
    transcript_ready = Signal(list)

    def __init__(self, whisper_service, session_id, mic_path, system_path, session_start_time):
        super().__init__()
        self.whisper_service = whisper_service
        self.session_id = session_id
        self.mic_path = mic_path
        self.system_path = system_path
        self.session_start_time = session_start_time

    def run(self):
        self.status_changed.emit('Transcribing audio...')
        entries = self.whisper_service.transcribe_session(
            self.session_id, self.mic_path, self.system_path, self.session_start_time
        )
        self.transcript_ready.emit(entries)
