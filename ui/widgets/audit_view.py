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
    AIResponseRepository, ChatFeedItemRepository, ToolCallRepository
)
from ui.styles import (
    STYLE_SHEET, BG_PRIMARY, BG_SECONDARY, BG_CARD,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
    FEED_QUESTION_BG, FEED_ANSWER_FADED, FEED_DIVIDER,
    AUDIT_STEP_COLOR, ERROR_COLOR
)


class CollapsibleSection(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QFrame()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(f'QFrame {{ padding: 4px 6px; border-radius: 3px; }} QFrame:hover {{ background-color: {BG_SECONDARY}; }}')
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._arrow = QLabel('\u25b8')
        self._arrow.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
        self._arrow.setFixedWidth(12)
        header_layout.addWidget(self._arrow)

        title_label = QLabel(title)
        title_label.setStyleSheet(f'color: {AUDIT_STEP_COLOR}; font-size: 11px; font-weight: 500;')
        header_layout.addWidget(title_label, 1)

        self._header.mousePressEvent = lambda _: self._toggle()
        layout.addWidget(self._header)

        self._body = QWidget()
        self._body.setVisible(False)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(18, 4, 0, 4)
        self._body_layout.setSpacing(2)
        layout.addWidget(self._body)

    def set_content(self, widget):
        self._body_layout.addWidget(widget)

    def _toggle(self):
        visible = not self._body.isVisible()
        self._body.setVisible(visible)
        self._arrow.setText('\u25be' if visible else '\u25b8')


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
        color = TEXT_DIM if step.status == StepStatus.COMPLETED else ERROR_COLOR
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


class AuditToolCallItem(QFrame):
    def __init__(self, record, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)

        name_label = QLabel(record.tool_name)
        name_label.setStyleSheet(f'color: {AUDIT_STEP_COLOR}; font-size: 11px; font-weight: 500;')
        header.addWidget(name_label, 1)

        dur = QLabel(f'{record.duration_ms}ms')
        dur.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
        header.addWidget(dur)

        layout.addLayout(header)

        query = record.arguments.get('query', '')
        if query:
            q_label = QLabel(f'Query: "{query}"')
            q_label.setWordWrap(True)
            q_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px; padding-left: 4px;')
            layout.addWidget(q_label)

        results = json.loads(record.result)
        section = CollapsibleSection(f'Results ({len(results)})')
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        for r in results:
            item_frame = QFrame()
            item_frame.setStyleSheet(f'QFrame {{ background-color: {BG_PRIMARY}; border-radius: 4px; padding: 6px; }}')
            item_layout = QVBoxLayout(item_frame)
            item_layout.setContentsMargins(6, 4, 6, 4)
            item_layout.setSpacing(2)

            source = r.get('filepath', r.get('source', ''))
            score = r.get('relevance_score', r.get('score', ''))
            meta_parts = []
            if source:
                meta_parts.append(source)
            if score:
                meta_parts.append(f'score: {score:.2f}' if isinstance(score, float) else f'score: {score}')

            if meta_parts:
                meta = QLabel(' \u00b7 '.join(meta_parts))
                meta.setWordWrap(True)
                meta.setStyleSheet(f'color: {AUDIT_STEP_COLOR}; font-size: 10px;')
                item_layout.addWidget(meta)

            text = r.get('text', r.get('content', ''))
            if text:
                snippet = text[:200] + '...' if len(text) > 200 else text
                text_label = QLabel(snippet)
                text_label.setWordWrap(True)
                text_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px; font-family: monospace;')
                item_layout.addWidget(text_label)

            content_layout.addWidget(item_frame)

        section.set_content(content)
        layout.addWidget(section)


class AuditInteractionGroup(QFrame):
    def __init__(self, interaction, steps, response, tool_calls, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'AuditInteractionGroup {{ background-color: {BG_CARD}; border-radius: 8px; }}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        query_label = QLabel(interaction.query_text)
        query_label.setWordWrap(True)
        query_label.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 600;')
        layout.addWidget(query_label)

        ts = QLabel(interaction.created_at.strftime('%H:%M:%S'))
        ts.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
        layout.addWidget(ts)

        if interaction.system_prompt:
            section = CollapsibleSection('System Prompt')
            prompt_label = QLabel(interaction.system_prompt)
            prompt_label.setWordWrap(True)
            prompt_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            prompt_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px; font-family: monospace;')
            section.set_content(prompt_label)
            layout.addWidget(section)

        if interaction.tools:
            section = CollapsibleSection(f'Tools ({len(interaction.tools)})')
            tools_widget = QWidget()
            tools_layout = QVBoxLayout(tools_widget)
            tools_layout.setContentsMargins(0, 0, 0, 0)
            tools_layout.setSpacing(2)
            for tool in interaction.tools:
                name = tool.get('name', tool.get('function', {}).get('name', ''))
                desc = tool.get('description', tool.get('function', {}).get('description', ''))
                text = f'{name}: {desc}' if desc else name
                t_label = QLabel(text)
                t_label.setWordWrap(True)
                t_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
                tools_layout.addWidget(t_label)
            section.set_content(tools_widget)
            layout.addWidget(section)

        if interaction.messages:
            section = CollapsibleSection(f'Messages ({len(interaction.messages)})')
            msgs_widget = QWidget()
            msgs_layout = QVBoxLayout(msgs_widget)
            msgs_layout.setContentsMargins(0, 0, 0, 0)
            msgs_layout.setSpacing(4)
            for msg in interaction.messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                if isinstance(content, list):
                    content = json.dumps(content)
                truncated = content[:300] + '...' if len(str(content)) > 300 else str(content)

                msg_frame = QFrame()
                msg_frame.setStyleSheet(f'QFrame {{ background-color: {BG_PRIMARY}; border-radius: 4px; }}')
                msg_layout = QVBoxLayout(msg_frame)
                msg_layout.setContentsMargins(6, 4, 6, 4)
                msg_layout.setSpacing(2)

                role_label = QLabel(role)
                role_label.setStyleSheet(f'color: {AUDIT_STEP_COLOR}; font-size: 10px; font-weight: 600;')
                msg_layout.addWidget(role_label)

                content_label = QLabel(truncated)
                content_label.setWordWrap(True)
                content_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
                msg_layout.addWidget(content_label)

                msgs_layout.addWidget(msg_frame)
            section.set_content(msgs_widget)
            layout.addWidget(section)

        for step in steps:
            layout.addWidget(AuditStepItem(step))

        for tc in tool_calls:
            layout.addWidget(AuditToolCallItem(tc))

        if response:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f'background-color: {FEED_DIVIDER};')
            layout.addWidget(sep)

            meta_parts = [response.model_used]
            if response.tokens_input:
                meta_parts.append(f'{response.tokens_input} in')
            if response.tokens_output:
                meta_parts.append(f'{response.tokens_output} out')
            meta_parts.append(f'{response.latency_ms}ms')

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
        self._tool_call_repo = ToolCallRepository(db)

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
            response = self._response_repo.get_by_interaction(interaction.id)
            tool_calls = self._tool_call_repo.get_by_interaction(interaction.id)
            events.append(('interaction', interaction.created_at, (interaction, steps, response, tool_calls)))

        events.sort(key=lambda e: e[1])

        for event_type, _, data in events:
            if event_type == 'feed':
                self._add_item(AuditFeedItem(data))
            elif event_type == 'interaction':
                interaction, steps, response, tool_calls = data
                self._add_item(AuditInteractionGroup(interaction, steps, response, tool_calls))

        if not events:
            empty = QLabel('No events in this session yet')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px; padding: 24px;')
            self._add_item(empty)

    def _add_item(self, widget):
        self._timeline.insertWidget(self._timeline.count() - 1, widget)
