import json

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Qt

from models import FeedItemType, StepType, StepStatus
from services.database import (
    Database, InteractionRepository, ExecutionStepRepository,
    AIResponseRepository, ChatFeedItemRepository
)
from ui.styles import (
    STYLE_SHEET, BG_PRIMARY, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
    FEED_QUESTION_BG, FEED_ANSWER_FADED,
    AUDIT_STEP_COLOR
)


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

        ts = QLabel(item.created_at.strftime('%H:%M:%S'))
        ts.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
        layout.addWidget(ts)


class AuditStepItem(QFrame):
    def __init__(self, step, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(2)

        labels = {
            StepType.LISTENING: 'Listening to conversation',
            StepType.SEARCHING_FILES: 'Looking through files',
            StepType.GENERATING: 'Thinking...',
        }

        row = QHBoxLayout()
        row.setSpacing(8)
        type_label = QLabel(labels[step.step_type])
        type_label.setStyleSheet(f'color: {AUDIT_STEP_COLOR}; font-size: 11px; font-style: italic;')
        row.addWidget(type_label, 1)

        status_text = step.status.value
        if step.status == StepStatus.COMPLETED:
            duration = (step.completed_at - step.started_at).total_seconds()
            status_text = f'{duration:.1f}s'
        elif step.status == StepStatus.FAILED:
            status_text = 'failed'

        status = QLabel(status_text)
        color = TEXT_DIM if step.status == StepStatus.COMPLETED else '#ff6b6b'
        status.setStyleSheet(f'color: {color}; font-size: 10px;')
        row.addWidget(status)
        layout.addLayout(row)

        if step.step_type == StepType.SEARCHING_FILES and step.details:
            details = json.loads(step.details)
            q_label = QLabel(f'Search: "{details["query"]}"')
            q_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px; padding-left: 4px;')
            layout.addWidget(q_label)
            f_label = QLabel(f'Found: {", ".join(details["matched_files"])}')
            f_label.setWordWrap(True)
            f_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px; padding-left: 4px;')
            layout.addWidget(f_label)


class AuditResponseItem(QFrame):
    def __init__(self, response, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        text = QLabel(response.text)
        text.setWordWrap(True)
        text.setStyleSheet(f'color: {FEED_ANSWER_FADED}; font-size: 12px;')
        layout.addWidget(text)

        meta_parts = [
            f'{response.tokens_output} tokens',
            f'{response.latency_ms}ms',
            response.created_at.strftime('%H:%M:%S'),
        ]
        meta = QLabel(' \u00b7 '.join(meta_parts))
        meta.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
        layout.addWidget(meta)


class AuditWindow(QWidget):
    def __init__(self, session_id: str, db: Database, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setFixedSize(600, 700)
        self.setWindowTitle('Session Audit')
        self.setStyleSheet(STYLE_SHEET + f'\nQWidget {{ background-color: {BG_PRIMARY}; }}')

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
            if event_type == 'feed':
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
