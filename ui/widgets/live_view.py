from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox, QScrollArea, QFrame,
    QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QGraphicsOpacityEffect

import qtawesome as qta

from models import (
    Brain, Question, Session, TranscriptEntry, SpeakerType,
    QueryType, StepType, StepStatus, ExecutionStep, AIResponse,
    ChatFeedItem, FeedItemType, generate_id
)
from services.database import SessionRepository, ChatFeedItemRepository, UserSettingsRepository
from services.conversation import ConversationContextCache
from services.export_service import build_export_markdown
from ui.styles import (
    STYLE_SHEET, BG_CARD, BG_CARD_HOVER,
    TEXT_SECONDARY, RECORDING_COLOR, ACCENT, USER_COLOR
)
from ui.threads import QueryExecutionThread
from ui.widgets.chat_feed import ChatFeedWidget

if TYPE_CHECKING:
    from menubar.app import MenuBarApp


class LiveQuestionRow(QFrame):
    clicked = Signal(object)

    def __init__(self, question: Question, parent=None):
        super().__init__(parent)
        self.question = question
        self.setObjectName('questionRow')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._active = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self._indicator = QLabel('')
        self._indicator.setFixedWidth(12)
        self._indicator.setStyleSheet(f'color: {TEXT_SECONDARY};')
        layout.addWidget(self._indicator)

        self._text_label = QLabel(question.text)
        self._text_label.setStyleSheet('color: #d0d0d0;')
        self._text_label.setWordWrap(True)
        self._text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._text_label, 1)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._indicator.setText('\u25b6')
            self._indicator.setStyleSheet(f'color: {ACCENT};')
            self.setStyleSheet(f'QFrame#questionRow {{ background-color: {BG_CARD_HOVER}; border-radius: 6px; }}')
        else:
            self._indicator.setText('')
            self._indicator.setStyleSheet(f'color: {TEXT_SECONDARY};')
            self.setStyleSheet('')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.question)
        super().mousePressEvent(event)


class LiveView(QWidget):
    navigate_to_picker = Signal()
    navigate_to_brain_edit = Signal(str)
    navigate_to_settings = Signal()
    navigate_to_history = Signal(str, str)
    pop_out_requested = Signal()

    def __init__(self, app: 'MenuBarApp'):
        super().__init__()
        self.app = app
        self._active_brain: Optional[Brain] = None
        self._session: Optional[Session] = None
        self._session_repo = SessionRepository(app.db)
        self._settings_repo = UserSettingsRepository(app.db)
        self._feed_repo = ChatFeedItemRepository(app.db)
        self._conversation_cache = ConversationContextCache()
        self._active_threads: dict[str, QueryExecutionThread] = {}
        self._answer_feed_ids: dict[str, str] = {}
        self._question_rows: list[LiveQuestionRow] = []
        self._active_question_id: Optional[str] = None
        self._final_transcripts: list[TranscriptEntry] = []
        self._partial_entry: Optional[TranscriptEntry] = None
        self.setStyleSheet(STYLE_SHEET)
        self._setup_ui()
        self.refresh_brains()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        layout.addLayout(self._build_header())
        layout.addWidget(self._build_transcript_area())
        layout.addWidget(self._build_questions_area())
        self._chat_feed = ChatFeedWidget()
        layout.addWidget(self._chat_feed, 1)
        layout.addLayout(self._build_input_area())

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(8)

        self._pop_out_btn = QPushButton()
        self._pop_out_btn.setObjectName('iconBtn')
        self._pop_out_btn.setIcon(qta.icon('mdi.open-in-new', color='#888888'))
        self._pop_out_btn.setFixedSize(24, 24)
        self._pop_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pop_out_btn.setToolTip('Open in window')
        self._pop_out_btn.clicked.connect(self.pop_out_requested.emit)
        header.addWidget(self._pop_out_btn)

        brain_icon = QLabel()
        brain_icon.setPixmap(qta.icon('mdi.brain', color=ACCENT).pixmap(18, 18))
        header.addWidget(brain_icon)

        self._brain_combo = QComboBox()
        self._brain_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._brain_combo.currentIndexChanged.connect(self._on_brain_changed)
        header.addWidget(self._brain_combo, 1)

        edit_btn = QPushButton()
        edit_btn.setObjectName('iconBtn')
        edit_btn.setIcon(qta.icon('mdi.pencil', color='#888888'))
        edit_btn.setFixedSize(24, 24)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(self._edit_current_brain)
        header.addWidget(edit_btn)

        add_btn = QPushButton()
        add_btn.setObjectName('iconBtn')
        add_btn.setIcon(qta.icon('mdi.plus', color='#888888'))
        add_btn.setFixedSize(24, 24)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self.navigate_to_picker.emit)
        header.addWidget(add_btn)

        history_btn = QPushButton()
        history_btn.setObjectName('iconBtn')
        history_btn.setIcon(qta.icon('mdi.history', color='#888888'))
        history_btn.setFixedSize(24, 24)
        history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        history_btn.setToolTip('Session history')
        history_btn.clicked.connect(
            lambda: self.navigate_to_history.emit(
                self._active_brain.id,
                self._session.id if self._session else ''
            ) if self._active_brain else None
        )
        header.addWidget(history_btn)

        audit_btn = QPushButton()
        audit_btn.setObjectName('iconBtn')
        audit_btn.setIcon(qta.icon('mdi.format-list-bulleted', color='#888888'))
        audit_btn.setFixedSize(24, 24)
        audit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        audit_btn.setToolTip('Session details')
        audit_btn.clicked.connect(self._show_audit)
        header.addWidget(audit_btn)

        settings_btn = QPushButton()
        settings_btn.setObjectName('iconBtn')
        settings_btn.setIcon(qta.icon('mdi.cog', color='#888888'))
        settings_btn.setFixedSize(24, 24)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.navigate_to_settings.emit)
        header.addWidget(settings_btn)

        return header

    def _edit_current_brain(self):
        if self._active_brain:
            self.navigate_to_brain_edit.emit(self._active_brain.id)

    def _show_audit(self):
        if not self._session:
            return
        from ui.widgets.audit_view import AuditWindow
        if hasattr(self, '_audit_window') and self._audit_window.isVisible():
            self._audit_window.raise_()
            return
        self._audit_window = AuditWindow(self._session.id, self.app.db)
        self._audit_window.show()

    def set_detached(self, detached: bool):
        if detached:
            self._pop_out_btn.setIcon(qta.icon('mdi.arrow-collapse', color='#888888'))
            self._pop_out_btn.setToolTip('Back to menu bar')
        else:
            self._pop_out_btn.setIcon(qta.icon('mdi.open-in-new', color='#888888'))
            self._pop_out_btn.setToolTip('Open in window')

    def _build_transcript_area(self) -> QWidget:
        self._transcript_container = QWidget()
        layout = QVBoxLayout(self._transcript_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._record_btn = QPushButton('Start Recording')
        self._record_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {RECORDING_COLOR};
                border: none;
                border-radius: 8px;
                padding: 12px;
                color: white;
                font-weight: 600;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #ff6666;
            }}
        ''')
        self._record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._record_btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self._record_btn)

        self._listening_bar = QWidget()
        self._listening_bar.setVisible(False)
        listening_layout = QHBoxLayout(self._listening_bar)
        listening_layout.setContentsMargins(10, 8, 10, 8)
        listening_layout.setSpacing(6)

        self._recording_dot = QLabel('\u2b24')
        self._recording_dot.setFixedSize(16, 16)
        self._recording_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._recording_dot.setStyleSheet(f'color: {RECORDING_COLOR}; font-size: 10px;')
        self._dot_opacity = QGraphicsOpacityEffect(self._recording_dot)
        self._recording_dot.setGraphicsEffect(self._dot_opacity)
        self._dot_anim = QPropertyAnimation(self._dot_opacity, b'opacity')
        self._dot_anim.setDuration(800)
        self._dot_anim.setKeyValueAt(0, 1.0)
        self._dot_anim.setKeyValueAt(0.5, 0.15)
        self._dot_anim.setKeyValueAt(1, 1.0)
        self._dot_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._dot_anim.setLoopCount(-1)
        listening_layout.addWidget(self._recording_dot)

        self._listening_text = QLabel('')
        self._listening_text.setStyleSheet(f'color: {TEXT_SECONDARY};')
        self._listening_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._listening_text.setWordWrap(False)
        listening_layout.addWidget(self._listening_text, 1)

        stop_btn = QPushButton()
        stop_btn.setObjectName('iconBtn')
        stop_btn.setIcon(qta.icon('mdi.stop', color='#888888'))
        stop_btn.setFixedSize(24, 24)
        stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stop_btn.clicked.connect(self._toggle_recording)
        listening_layout.addWidget(stop_btn)

        self._listening_bar.setStyleSheet(f'''
            QWidget {{
                background-color: {BG_CARD};
                border-radius: 8px;
            }}
        ''')
        layout.addWidget(self._listening_bar)

        return self._transcript_container

    def _build_questions_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel('QUESTIONS')
        label.setObjectName('sectionLabel')
        layout.addWidget(label)

        self._questions_scroll = QScrollArea()
        self._questions_scroll.setWidgetResizable(True)
        self._questions_scroll.setMaximumHeight(160)
        self._questions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._questions_widget = QWidget()
        self._questions_layout = QVBoxLayout(self._questions_widget)
        self._questions_layout.setSpacing(4)
        self._questions_layout.setContentsMargins(0, 0, 0, 0)
        self._questions_layout.addStretch()
        self._questions_scroll.setWidget(self._questions_widget)
        layout.addWidget(self._questions_scroll)

        return container

    def _build_input_area(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText('Ask anything...')
        self._input.returnPressed.connect(self._send_freeform)
        row.addWidget(self._input, 1)

        send_btn = QPushButton()
        send_btn.setObjectName('iconBtn')
        send_btn.setIcon(qta.icon('mdi.send', color='#888888'))
        send_btn.setFixedSize(28, 28)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.clicked.connect(self._send_freeform)
        row.addWidget(send_btn)

        return row

    def refresh_brains(self):
        self._brain_combo.blockSignals(True)
        self._brain_combo.clear()
        brains = self.app.brain_repo.get_all()
        for brain in brains:
            self._brain_combo.addItem(brain.name, brain.id)
        if brains:
            self._active_brain = brains[0]
            self._brain_combo.setCurrentIndex(0)
            self._start_new_session()
            self.load_questions(brains[0].id)
            self._load_session_feed()
        self._brain_combo.blockSignals(False)

    def set_active_brain(self, brain_id: str):
        for i in range(self._brain_combo.count()):
            if self._brain_combo.itemData(i) == brain_id:
                self._brain_combo.setCurrentIndex(i)
                return

    def _on_brain_changed(self, index):
        if index < 0:
            return
        brain_id = self._brain_combo.itemData(index)
        self._active_brain = self.app.brain_repo.get(brain_id)
        self._cleanup_threads()
        self._start_new_session()
        self.load_questions(brain_id)
        self._load_session_feed()

    def _start_new_session(self):
        if not self._active_brain:
            return
        if self._session and not self._session.ended_at:
            self._session_repo.end_session(self._session.id)
        self._session = Session(
            name=self._active_brain.name,
            current_brain_id=self._active_brain.id
        )
        self._session_repo.create(self._session)

    def _load_session_feed(self):
        self._chat_feed.clear_feed()

    def _cleanup_threads(self):
        for thread in self._active_threads.values():
            thread.quit()
            thread.wait(2000)
        self._active_threads.clear()
        self._answer_feed_ids.clear()

    def _toggle_recording(self):
        if self.app.audio_service.is_recording():
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if self._session and not self._session.ended_at:
            self._session_repo.end_session(self._session.id)
        brain_name = self._active_brain.name if self._active_brain else 'Recording'
        session = Session(
            name=brain_name,
            current_brain_id=self._active_brain.id if self._active_brain else None
        )
        self.app.audio_service.start_session(session, self._on_transcript)
        self._session = self.app.audio_service.get_current_session()
        self._final_transcripts = []
        self._partial_entry = None
        self._record_btn.setVisible(False)
        self._listening_bar.setVisible(True)
        self._listening_text.setText('')
        self._dot_anim.start()

    def _stop_recording(self):
        recording_session_id = self._session.id if self._session else None
        self.app.audio_service.stop_session()
        self._record_btn.setVisible(True)
        self._listening_bar.setVisible(False)
        self._dot_anim.stop()
        self._dot_opacity.setOpacity(1.0)
        if recording_session_id:
            self._add_export_item(recording_session_id)
            self._maybe_show_feedback(recording_session_id)
        self._start_new_session()

    def _maybe_show_feedback(self, session_id: str):
        settings = self._settings_repo.get()
        if settings.feedback_opt_in is False:
            return
        item = self._chat_feed.add_feedback_item()
        item.rated.connect(lambda rating, sid=session_id: self._submit_feedback(sid, rating))
        item.dismissed.connect(lambda: None)

    def _submit_feedback(self, session_id: str, rating: int):
        self._session_repo.set_rating(session_id, rating)
        from services.feedback_service import SessionPackager, FeedbackClient
        package = SessionPackager(self.app.db).package(session_id, rating)
        FeedbackClient().submit(package)

    def _add_export_item(self, session_id: str):
        item = self._chat_feed.add_export_item()
        item.clicked.connect(lambda sid=session_id: self._export_session(sid))

    def _export_session(self, session_id: str):
        text = build_export_markdown(session_id, self.app.db)
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Session', 'session-export.md', 'Markdown Files (*.md)'
        )
        if path:
            with open(path, 'w') as f:
                f.write(text)

    def _on_transcript(self, entry: TranscriptEntry, is_final: bool):
        if is_final:
            self._final_transcripts.append(entry)
            self._partial_entry = None
        else:
            self._partial_entry = entry
        last = entry.text
        if len(last) > 60:
            last = '...' + last[-57:]
        color = USER_COLOR if entry.speaker == SpeakerType.USER else TEXT_SECONDARY
        self._listening_text.setStyleSheet(f'color: {color};')
        self._listening_text.setText(last)

    def load_questions(self, brain_id: str):
        while self._questions_layout.count() > 1:
            item = self._questions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._question_rows = []
        questions = self.app.question_repo.get_by_brain(brain_id)
        for q in questions:
            row = LiveQuestionRow(q)
            row.clicked.connect(self._on_question_clicked)
            self._question_rows.append(row)
            self._questions_layout.insertWidget(self._questions_layout.count() - 1, row)

    def _on_question_clicked(self, question: Question):
        self._set_active_question(question.id)
        self._do_execute_query(question.text, QueryType.PRESET, question.id)

    def _set_active_question(self, question_id: Optional[str]):
        self._active_question_id = question_id
        for row in self._question_rows:
            row.set_active(row.question.id == question_id)

    def _send_freeform(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._set_active_question(None)
        self._do_execute_query(text, QueryType.FREEFORM)

    def _do_execute_query(self, query_text: str, query_type: QueryType, question_id: str = None):
        brain = self._active_brain
        if not brain or not self._session:
            return

        session_id = self._session.id
        thread_id = generate_id()

        transcript = self._final_transcripts.copy()
        if self._partial_entry:
            transcript.append(self._partial_entry)

        pos = self._feed_repo.get_next_position(session_id)

        if transcript:
            transcript_text = '\n'.join(e.text for e in transcript[-5:])
            self._feed_repo.create(ChatFeedItem(
                session_id=session_id,
                item_type=FeedItemType.TRANSCRIPT,
                content=transcript_text,
                position=pos
            ))
            self._chat_feed.add_transcript_divider(transcript_text)
            pos += 1

        self._feed_repo.create(ChatFeedItem(
            session_id=session_id,
            item_type=FeedItemType.QUESTION,
            content=query_text,
            position=pos
        ))
        self._chat_feed.add_question(query_text)
        pos += 1

        answer_item = ChatFeedItem(
            session_id=session_id,
            item_type=FeedItemType.ANSWER,
            content='',
            position=pos,
            thread_id=thread_id
        )
        self._feed_repo.create(answer_item)
        self._answer_feed_ids[thread_id] = answer_item.id
        self._chat_feed.add_answer(thread_id)

        conversation = self._conversation_cache.get(session_id, brain.id)
        snap = conversation.snapshot()
        snap.add_transcript_entries(transcript)

        thread = QueryExecutionThread(
            db=self.app.db,
            embedder=self.app.embedder,
            session_id=session_id,
            brain=brain,
            query_text=query_text,
            transcript=transcript,
            query_type=query_type,
            question_id=question_id,
            thread_id=thread_id,
            conversation_snapshot=snap
        )
        thread.step_update.connect(self._on_step_update)
        thread.delta.connect(self._on_delta)
        thread.complete.connect(self._on_complete)
        thread.tool_call.connect(self._on_tool_call)
        thread.finished.connect(lambda tid=thread_id: self._on_thread_finished(tid))
        self._active_threads[thread_id] = thread
        thread.start()

    def _on_step_update(self, thread_id: str, step: ExecutionStep):
        if step.status == StepStatus.COMPLETED:
            self._chat_feed.remove_status(thread_id)
            return
        labels = {
            StepType.LISTENING: 'Listening to the conversation',
            StepType.SEARCHING_FILES: 'Looking through your files',
            StepType.READING_FILE: 'Reading file...',
            StepType.GENERATING: 'Thinking...',
        }
        self._chat_feed.update_status(thread_id, labels.get(step.step_type, 'Working...'))

    def _on_delta(self, thread_id: str, text: str):
        self._chat_feed.append_answer_delta(thread_id, text)

    def _on_tool_call(self, thread_id: str, detail):
        self._chat_feed.add_tool_call(thread_id, detail)

    def _on_complete(self, thread_id: str, response: AIResponse):
        self._chat_feed.remove_status(thread_id)
        self._chat_feed.set_answer_complete(thread_id, response.file_references)
        feed_id = self._answer_feed_ids.pop(thread_id, None)
        if feed_id:
            self._feed_repo.update_content(feed_id, response.text)

    def _on_thread_finished(self, thread_id: str):
        self._active_threads.pop(thread_id, None)
