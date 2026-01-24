from PySide6.QtCore import QThread, Signal

from models import Brain, AIResponse, ExecutionStep, QueryType, TranscriptEntry
from services.database import Database
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks


class QueryExecutionThread(QThread):
    step_update = Signal(object)   # ExecutionStep
    delta = Signal(str)            # streaming text chunk
    complete = Signal(object)      # AIResponse
    error = Signal(str)

    def __init__(self, db: Database, embedder, session_id: str, brain: Brain,
                 query_text: str, transcript: list[TranscriptEntry],
                 query_type: QueryType = QueryType.FREEFORM,
                 question_id: str = None):
        super().__init__()
        self.db = db
        self.embedder = embedder
        self.session_id = session_id
        self.brain = brain
        self.query_text = query_text
        self.transcript = transcript
        self.query_type = query_type
        self.question_id = question_id

    def run(self):
        service = QueryExecutionService(self.db, self.embedder)

        ctx = QueryContext(
            session_id=self.session_id,
            brain=self.brain,
            query_text=self.query_text,
            transcript=self.transcript,
            query_type=self.query_type,
            question_id=self.question_id
        )

        callbacks = ExecutionCallbacks(
            on_step=lambda step: self.step_update.emit(step),
            on_delta=lambda text: self.delta.emit(text),
            on_complete=lambda resp: self.complete.emit(resp)
        )

        service.execute(ctx, callbacks)
