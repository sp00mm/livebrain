import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Qt

from models import FeedItemType, StepType, StepStatus, SpeakerType
from services.database import (
    Database, InteractionRepository, ExecutionStepRepository,
    AIResponseRepository, TranscriptEntryRepository, ChatFeedItemRepository
)
from ui.styles import (
    STYLE_SHEET, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
    FEED_QUESTION_BG, FEED_ANSWER_ACTIVE, FEED_ANSWER_FADED,
    AUDIT_STEP_COLOR
)


class AuditTranscriptItem(QFrame):
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        is_user = entry.speaker == SpeakerType.USER
        icon_name = 'mdi.microphone' if is_user else 'mdi.volume-high'
        icon = QLabel()
        icon.setPixmap(qta.icon(icon_name, color=TEXT_DIM).pixmap(14, 14))
        icon.setFixedWidth(14)
        layout.addWidget(icon)

        speaker = 'You' if is_user else 'Other'
        speaker_label = QLabel(speaker)
        speaker_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px; font-weight: 500;')
        speaker_label.setFixedWidth(36)
        layout.addWidget(speaker_label)

        text = QLabel(entry.text)
        text.setWordWrap(True)
        text.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')
        layout.addWidget(text, 1)

        if entry.timestamp:
            ts = QLabel(entry.timestamp.strftime('%H:%M:%S'))
            ts.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
            layout.addWidget(ts)


class AuditFeedItem(QFrame):
    def __init__(self, item, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        if item.item_type == FeedItemType.QUESTION:
            label = QLabel(item.content)
            label.setWordWrap(True)
            label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px; font-weight: 500;')
            layout.addWidget(label)
            self.setStyleSheet(f'QFrame {{ background-color: {FEED_QUESTION_BG}; border-radius: 6px; }}')
        elif item.item_type == FeedItemType.ANSWER:
            label = QLabel(item.content)
            label.setWordWrap(True)
            label.setStyleSheet(f'color: {FEED_ANSWER_FADED}; font-size: 12px;')
            layout.addWidget(label)
        elif item.item_type == FeedItemType.TRANSCRIPT:
            label = QLabel(item.content)
            label.setWordWrap(True)
            label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')
            layout.addWidget(label)

        if item.created_at:
            ts = QLabel(item.created_at.strftime('%H:%M:%S'))
            ts.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
            layout.addWidget(ts)


class AuditStepItem(QFrame):
    def __init__(self, step, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(8)

        labels = {
            StepType.LISTENING: 'Listening to conversation',
            StepType.SEARCHING_FILES: 'Looking through files',
            StepType.GENERATING: 'Thinking...',
        }
        type_label = QLabel(labels.get(step.step_type, 'Working...'))
        type_label.setStyleSheet(f'color: {AUDIT_STEP_COLOR}; font-size: 11px; font-style: italic;')
        layout.addWidget(type_label, 1)

        status_text = step.status.value
        if step.status == StepStatus.COMPLETED and step.started_at and step.completed_at:
            duration = (step.completed_at - step.started_at).total_seconds()
            status_text = f'{duration:.1f}s'
        elif step.status == StepStatus.FAILED:
            status_text = 'failed'

        status = QLabel(status_text)
        color = TEXT_DIM if step.status == StepStatus.COMPLETED else '#ff6b6b'
        status.setStyleSheet(f'color: {color}; font-size: 10px;')
        layout.addWidget(status)


class AuditResponseItem(QFrame):
    def __init__(self, response, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        text = QLabel(response.text)
        text.setWordWrap(True)
        text.setStyleSheet(f'color: {FEED_ANSWER_FADED}; font-size: 12px;')
        layout.addWidget(text)

        meta_parts = []
        if response.tokens_output:
            meta_parts.append(f'{response.tokens_output} tokens')
        if response.latency_ms:
            meta_parts.append(f'{response.latency_ms}ms')
        if response.created_at:
            meta_parts.append(response.created_at.strftime('%H:%M:%S'))

        if meta_parts:
            meta = QLabel(' · '.join(meta_parts))
            meta.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
            layout.addWidget(meta)


class AuditWindow(QWidget):
    def __init__(self, session_id: str, db: Database, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setFixedSize(600, 700)
        self.setWindowTitle('Session Audit')
        self.setStyleSheet(STYLE_SHEET)

        self._transcript_repo = TranscriptEntryRepository(db)
        self._feed_repo = ChatFeedItemRepository(db)
        self._interaction_repo = InteractionRepository(db)
        self._step_repo = ExecutionStepRepository(db)
        self._response_repo = AIResponseRepository(db)

        self._setup_ui()
        self._load_session(session_id)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel('Session Audit')
        title.setStyleSheet(f'color: {TEXT_PRIMARY}; font-weight: 600; font-size: 14px;')
        header.addWidget(title, 1)

        close_btn = QPushButton()
        close_btn.setObjectName('iconBtn')
        close_btn.setIcon(qta.icon('mdi.close', color='#888888'))
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)

        layout.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._timeline = QVBoxLayout(self._container)
        self._timeline.setContentsMargins(0, 0, 0, 0)
        self._timeline.setSpacing(4)
        self._timeline.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

    def _load_session(self, session_id):
        events = []

        transcripts = self._transcript_repo.get_by_session(session_id)
        for t in transcripts:
            events.append(('transcript', t.timestamp, t))

        feed_items = self._feed_repo.get_by_session(session_id)
        for item in feed_items:
            events.append(('feed', item.created_at, item))

        interactions = self._interaction_repo.get_by_session(session_id)
        for interaction in interactions:
            steps = self._step_repo.get_by_interaction(interaction.id)
            for step in steps:
                events.append(('step', step.started_at, step))
            response = self._response_repo.get_by_interaction(interaction.id)
            if response:
                events.append(('response', response.created_at, response))

        events.sort(key=lambda e: e[1])

        for event_type, _, data in events:
            if event_type == 'transcript':
                self._add_item(AuditTranscriptItem(data))
            elif event_type == 'feed':
                self._add_item(AuditFeedItem(data))
            elif event_type == 'step':
                self._add_item(AuditStepItem(data))
            elif event_type == 'response':
                self._add_item(AuditResponseItem(data))

        if not events:
            empty = QLabel('No events in this session yet')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px; padding: 24px;')
            self._add_item(empty)

    def _add_item(self, widget):
        self._timeline.insertWidget(self._timeline.count() - 1, widget)
