from typing import Callable, Optional

from models import Session, TranscriptEntry, SpeakerType, now
from services.database import Database, SessionRepository, TranscriptEntryRepository
from ui.threads.audio_thread import AudioThread
from audio.capture.macos import MacOSMicCapture, MacOSSystemCapture
from audio.transcription import AppleSpeechTranscriber


class AudioService:
    def __init__(self, db: Database):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.transcript_repo = TranscriptEntryRepository(db)
        self._current_thread: Optional[AudioThread] = None
        self._current_session: Optional[Session] = None
        self._partial_transcripts: dict[str, str] = {}

    def check_permissions(self) -> dict[str, bool]:
        mic = MacOSMicCapture()
        speech = AppleSpeechTranscriber()
        system = MacOSSystemCapture()

        return {
            'microphone': mic.is_available(),
            'speech_recognition': speech.is_available(),
            'system_audio': system.is_available()
        }

    def request_permissions(self, callback: Callable[[dict[str, bool]], None]) -> None:
        results = {'microphone': False, 'speech_recognition': False, 'system_audio': False}
        pending = 3

        def check_done():
            nonlocal pending
            pending -= 1
            if pending == 0:
                callback(results)

        mic = MacOSMicCapture()
        speech = AppleSpeechTranscriber()
        system = MacOSSystemCapture()

        def on_mic(granted):
            results['microphone'] = granted
            check_done()

        def on_speech(granted):
            results['speech_recognition'] = granted
            check_done()

        def on_system(granted):
            results['system_audio'] = granted
            check_done()

        mic.request_permission(on_mic)
        speech.request_permission(on_speech)
        system.request_permission(on_system)

    def start_session(self, session: Session, on_transcript: Callable[[TranscriptEntry, bool], None]) -> AudioThread:
        if self._current_thread:
            self.stop_session()

        session.is_live = True
        self.session_repo.create(session)
        self._current_session = session
        self._partial_transcripts = {}

        self._current_thread = AudioThread(session.id)

        def handle_transcript(speaker: str, text: str, confidence: float, is_final: bool):
            speaker_type = SpeakerType(speaker)

            if is_final:
                entry = TranscriptEntry(
                    session_id=session.id,
                    speaker=speaker_type,
                    text=text,
                    confidence=confidence,
                    timestamp=now()
                )
                self.transcript_repo.create(entry)
                self._partial_transcripts[speaker] = ''
                on_transcript(entry, True)
            else:
                self._partial_transcripts[speaker] = text
                partial = TranscriptEntry(
                    session_id=session.id,
                    speaker=speaker_type,
                    text=text,
                    confidence=confidence,
                    timestamp=now()
                )
                on_transcript(partial, False)

        self._current_thread.transcript_update.connect(handle_transcript)
        self._current_thread.start()

        return self._current_thread

    def stop_session(self) -> Optional[Session]:
        if not self._current_thread or not self._current_session:
            return None

        self._current_thread.stop_recording()
        self._current_thread.wait()
        self._current_thread = None

        for speaker, text in self._partial_transcripts.items():
            if text.strip():
                entry = TranscriptEntry(
                    session_id=self._current_session.id,
                    speaker=SpeakerType(speaker),
                    text=text.strip(),
                    confidence=0.5,
                    timestamp=now()
                )
                self.transcript_repo.create(entry)

        self.session_repo.end_session(self._current_session.id)
        session = self.session_repo.get(self._current_session.id)
        self._current_session = None
        self._partial_transcripts = {}

        return session

    def get_current_session(self) -> Optional[Session]:
        return self._current_session

    def is_recording(self) -> bool:
        return self._current_thread is not None and self._current_thread.isRunning()
