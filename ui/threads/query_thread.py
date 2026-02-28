from PySide6.QtCore import QThread, Signal

from models import Brain, AIResponse, ExecutionStep, QueryType, TranscriptEntry
from services.database import Database
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks


class QueryExecutionThread(QThread):
    step_update = Signal(str, object)   # (thread_id, ExecutionStep)
    delta = Signal(str, str)            # (thread_id, text chunk)
    complete = Signal(str, object)      # (thread_id, AIResponse)
    error = Signal(str, str)            # (thread_id, error message)

    def __init__(self, db: Database, embedder, session_id: str, brain: Brain,
                 query_text: str, transcript: list[TranscriptEntry],
                 query_type: QueryType = QueryType.FREEFORM,
                 question_id: str = None,
                 thread_id: str = None,
                 conversation_snapshot=None):
        super().__init__()
        self.db = db
        self.embedder = embedder
        self.session_id = session_id
        self.brain = brain
        self.query_text = query_text
        self.transcript = transcript
        self.query_type = query_type
        self.question_id = question_id
        self.thread_id = thread_id or ''
        self.conversation_snapshot = conversation_snapshot

    def run(self):
        service = QueryExecutionService(self.db, self.embedder)

        ctx = QueryContext(
            session_id=self.session_id,
            brain=self.brain,
            query_text=self.query_text,
            transcript=self.transcript,
            query_type=self.query_type,
            question_id=self.question_id,
            conversation_snapshot=self.conversation_snapshot
        )

        callbacks = ExecutionCallbacks(
            on_step=lambda step: self.step_update.emit(self.thread_id, step),
            on_delta=lambda text: self.delta.emit(self.thread_id, text),
            on_complete=lambda resp: self.complete.emit(self.thread_id, resp)
        )

        service.execute(ctx, callbacks)
