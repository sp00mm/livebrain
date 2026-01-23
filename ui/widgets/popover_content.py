import os
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QLabel, QComboBox,
    QScrollArea, QFrame, QProgressDialog, QMessageBox,
    QStackedWidget, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal

import qtawesome as qta

from models import Session, TranscriptEntry, SpeakerType, QueryType, StepType, ExecutionStep, Brain, Question
from services.embedder import Embedder
from ui.threads import ModelDownloadThread, QueryExecutionThread

if TYPE_CHECKING:
    from menubar.app import MenuBarApp


STYLE_SHEET = '''
QWidget {
    background: transparent;
    color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    font-size: 13px;
}
QPushButton {
    background-color: #3a3a3a;
    border: 1px solid #4a4a4a;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e0e0e0;
}
QPushButton:hover {
    background-color: #454545;
}
QPushButton:pressed {
    background-color: #2a2a2a;
}
QPushButton#downloadBtn {
    background-color: #4CAF50;
    border: none;
    font-weight: 500;
}
QPushButton#iconBtn {
    background: transparent;
    border: none;
    padding: 4px;
    border-radius: 4px;
    min-width: 24px;
    max-width: 24px;
}
QPushButton#iconBtn:hover {
    background-color: #404040;
}
QLineEdit {
    background-color: #1e1e1e;
    border: 1px solid #3a3a3a;
    border-radius: 8px;
    padding: 10px 12px;
    color: #e0e0e0;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #505050;
}
QTextEdit {
    background-color: #1e1e1e;
    border: none;
    border-radius: 8px;
    padding: 12px;
    color: #e0e0e0;
    font-size: 13px;
}
QTextEdit#responseBox {
    background-color: #1a1a1a;
    border-radius: 10px;
}
QLabel {
    color: #b0b0b0;
}
QLabel#sectionLabel {
    color: #707070;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QLabel#liveLabel {
    font-weight: 600;
    font-size: 13px;
}
QLabel#transcriptUser {
    color: #ffffff;
    font-size: 13px;
}
QLabel#transcriptOther {
    color: #5fb85f;
    font-size: 13px;
}
QComboBox {
    background-color: transparent;
    border: none;
    padding: 4px 8px;
    color: #e0e0e0;
    font-size: 13px;
}
QComboBox:hover {
    background-color: #353535;
    border-radius: 4px;
}
QComboBox::drop-down {
    border: none;
    width: 16px;
}
QComboBox::down-arrow {
    image: none;
}
QComboBox QAbstractItemView {
    background-color: #2a2a2a;
    border: 1px solid #404040;
    border-radius: 6px;
    selection-background-color: #404040;
    color: #e0e0e0;
    padding: 4px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QFrame#questionRow {
    background-color: #252525;
    border-radius: 6px;
}
QFrame#questionRow:hover {
    background-color: #2d2d2d;
}
'''


class QuestionRow(QFrame):
    clicked = Signal(object)
    edit_clicked = Signal(object)

    def __init__(self, question: Question, parent=None):
        super().__init__(parent)
        self.question = question
        self.setObjectName('questionRow')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 6, 8)
        layout.setSpacing(8)

        self._text_label = QLabel(question.text)
        self._text_label.setStyleSheet('color: #d0d0d0;')
        self._text_label.setWordWrap(True)
        self._text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._text_label, 1)

        edit_btn = QPushButton()
        edit_btn.setObjectName('iconBtn')
        edit_btn.setIcon(qta.icon('mdi.pencil', color='#666666'))
        edit_btn.setFixedSize(24, 24)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(self._on_edit)
        layout.addWidget(edit_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.question)
        super().mousePressEvent(event)

    def _on_edit(self):
        self.edit_clicked.emit(self.question)


class PopoverContent(QWidget):
    def __init__(self, app: 'MenuBarApp'):
        super().__init__()
        self.app = app
        self._final_transcripts: list[TranscriptEntry] = []
        self._partial_entry: Optional[TranscriptEntry] = None
        self._query_thread = None
        self._duration_timer = QTimer()
        self._duration_timer.timeout.connect(self._update_duration)
        self._recording_seconds = 0

        self._current_brain: Optional[Brain] = None
        self._questions: list[Question] = []
        self._editing_brain: Optional[Brain] = None
        self._editing_question: Optional[Question] = None

        self.setStyleSheet(STYLE_SHEET)
        self._setup_ui()
        self._check_models()
        self._load_brains()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._stack.addWidget(self._build_main_view())
        self._stack.addWidget(self._build_brain_edit_view())
        self._stack.addWidget(self._build_question_edit_view())

    def _build_main_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        self._models_btn = QPushButton('Download AI Models')
        self._models_btn.setObjectName('downloadBtn')
        self._models_btn.clicked.connect(self._download_models)
        self._models_btn.setVisible(False)
        layout.addWidget(self._models_btn)

        header = QHBoxLayout()
        header.setSpacing(8)

        live_container = QHBoxLayout()
        live_container.setSpacing(6)
        self._live_dot = QLabel('●')
        self._live_dot.setStyleSheet('color: #666666; font-size: 14px;')
        live_container.addWidget(self._live_dot)
        self._live_label = QLabel('LIVE')
        self._live_label.setObjectName('liveLabel')
        self._live_label.setStyleSheet('color: #666666;')
        live_container.addWidget(self._live_label)
        header.addLayout(live_container)

        header.addStretch()

        brain_label = QLabel('Brain:')
        brain_label.setStyleSheet('color: #888888;')
        header.addWidget(brain_label)

        self._brain_combo = QComboBox()
        self._brain_combo.currentIndexChanged.connect(self._on_brain_changed)
        header.addWidget(self._brain_combo)

        self._add_brain_btn = QPushButton()
        self._add_brain_btn.setObjectName('iconBtn')
        self._add_brain_btn.setIcon(qta.icon('mdi.plus', color='#888888'))
        self._add_brain_btn.setFixedSize(24, 24)
        self._add_brain_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_brain_btn.clicked.connect(self._create_brain)
        header.addWidget(self._add_brain_btn)

        self._edit_brain_btn = QPushButton()
        self._edit_brain_btn.setObjectName('iconBtn')
        self._edit_brain_btn.setIcon(qta.icon('mdi.pencil', color='#888888'))
        self._edit_brain_btn.setFixedSize(24, 24)
        self._edit_brain_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_brain_btn.clicked.connect(self._show_brain_edit)
        header.addWidget(self._edit_brain_btn)

        layout.addLayout(header)

        self._transcript_container = QWidget()
        self._transcript_layout = QVBoxLayout(self._transcript_container)
        self._transcript_layout.setSpacing(4)
        self._transcript_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._transcript_container)

        layout.addWidget(self._section_label('QUESTIONS'))

        self._questions_scroll = QScrollArea()
        self._questions_scroll.setWidgetResizable(True)
        self._questions_scroll.setMaximumHeight(140)
        self._questions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._questions_container = QWidget()
        self._questions_layout = QVBoxLayout(self._questions_container)
        self._questions_layout.setSpacing(6)
        self._questions_layout.setContentsMargins(0, 4, 0, 0)
        self._questions_layout.addStretch()
        self._questions_scroll.setWidget(self._questions_container)
        layout.addWidget(self._questions_scroll)

        add_q_row = QHBoxLayout()
        add_q_row.setContentsMargins(0, 0, 0, 0)
        self._add_question_btn = QPushButton()
        self._add_question_btn.setObjectName('iconBtn')
        self._add_question_btn.setIcon(qta.icon('mdi.plus-circle-outline', color='#555555'))
        self._add_question_btn.setFixedSize(24, 24)
        self._add_question_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_question_btn.setToolTip('Add question')
        self._add_question_btn.clicked.connect(self._create_question)
        add_q_row.addWidget(self._add_question_btn)
        add_q_row.addStretch()
        layout.addLayout(add_q_row)

        layout.addWidget(self._section_label('LIVEBRAIN SAYS'))

        self._response = QTextEdit()
        self._response.setObjectName('responseBox')
        self._response.setReadOnly(True)
        self._response.setPlaceholderText('')
        self._response.setMinimumHeight(80)
        self._response.setMaximumHeight(120)
        layout.addWidget(self._response)

        self._query_status = QLabel('')
        self._query_status.setStyleSheet('color: #606060; font-size: 11px; font-style: italic;')
        layout.addWidget(self._query_status)

        layout.addStretch()

        self._ask_input = QLineEdit()
        self._ask_input.setPlaceholderText('Ask this brain anything...')
        self._ask_input.returnPressed.connect(self._ask_brain)
        layout.addWidget(self._ask_input)

        return view

    def _build_brain_edit_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        back_btn = QPushButton()
        back_btn.setObjectName('iconBtn')
        back_btn.setIcon(qta.icon('mdi.arrow-left', color='#6eb5ff'))
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        header.addWidget(back_btn)
        header.addStretch()
        title = QLabel('Edit Brain')
        title.setStyleSheet('font-weight: 600; font-size: 14px; color: #e0e0e0;')
        header.addWidget(title)
        header.addStretch()
        header.addSpacing(28)
        layout.addLayout(header)

        # Name field
        layout.addWidget(QLabel('Name'))
        self._brain_name_input = QLineEdit()
        layout.addWidget(self._brain_name_input)

        # Description field
        layout.addWidget(QLabel('Description'))
        self._brain_desc_input = QLineEdit()
        layout.addWidget(self._brain_desc_input)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        delete_btn = QPushButton('Delete')
        delete_btn.setStyleSheet('background-color: #4a2020; border-color: #5a2525;')
        delete_btn.clicked.connect(self._delete_brain)
        btn_row.addWidget(delete_btn)

        save_btn = QPushButton('Save')
        save_btn.setStyleSheet('background-color: #2d4a2d; border-color: #3a5a3a;')
        save_btn.clicked.connect(self._save_brain)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        return view

    def _build_question_edit_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        back_btn = QPushButton()
        back_btn.setObjectName('iconBtn')
        back_btn.setIcon(qta.icon('mdi.arrow-left', color='#6eb5ff'))
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        header.addWidget(back_btn)
        header.addStretch()
        title = QLabel('Edit Question')
        title.setStyleSheet('font-weight: 600; font-size: 14px; color: #e0e0e0;')
        header.addWidget(title)
        header.addStretch()
        header.addSpacing(28)
        layout.addLayout(header)

        # Question text field
        layout.addWidget(QLabel('Question'))
        self._question_text_input = QLineEdit()
        layout.addWidget(self._question_text_input)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        delete_btn = QPushButton('Delete')
        delete_btn.setStyleSheet('background-color: #4a2020; border-color: #5a2525;')
        delete_btn.clicked.connect(self._delete_question)
        btn_row.addWidget(delete_btn)

        save_btn = QPushButton('Save')
        save_btn.setStyleSheet('background-color: #2d4a2d; border-color: #3a5a3a;')
        save_btn.clicked.connect(self._save_question)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        return view

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName('sectionLabel')
        return label

    def _check_models(self):
        model_dir = Embedder.get_model_dir()
        model_file = os.path.join(model_dir, 'onnx', 'model_q4.onnx')
        if not os.path.exists(model_file):
            self._models_btn.setVisible(True)

    def _download_models(self):
        model_dir = os.path.dirname(Embedder.get_model_dir())

        self._progress = QProgressDialog('Downloading models...', 'Cancel', 0, 100, self)
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setAutoClose(False)
        self._progress.canceled.connect(self._cancel_download)

        self._download_thread = ModelDownloadThread(self.app.updater, model_dir)
        self._download_thread.progress.connect(self._update_progress)
        self._download_thread.finished.connect(self._download_complete)
        self._download_thread.start()

        self._progress.show()

    def _update_progress(self, percent, downloaded, total):
        self._progress.setValue(percent)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        self._progress.setLabelText(f'Downloading... {mb_downloaded:.1f} MB / {mb_total:.1f} MB')

    def _cancel_download(self):
        if hasattr(self, '_download_thread'):
            self._download_thread.terminate()

    def _download_complete(self, success, error):
        self._progress.close()
        if success:
            self._models_btn.setVisible(False)
            self.app._init_embedder()
            QMessageBox.information(self, 'Done', 'Models downloaded successfully!')
        else:
            QMessageBox.critical(self, 'Error', f'Download failed: {error}')

    def _load_brains(self):
        self._brain_combo.blockSignals(True)
        self._brain_combo.clear()
        brains = self.app.brain_repo.get_all()
        for brain in brains:
            self._brain_combo.addItem(brain.name, brain.id)

        if brains:
            self._current_brain = brains[0]
            self._brain_combo.setCurrentIndex(0)
            self._load_questions()

        self._brain_combo.blockSignals(False)

    def _on_brain_changed(self, index):
        if index < 0:
            return
        brain_id = self._brain_combo.itemData(index)
        self._current_brain = self.app.brain_repo.get(brain_id)
        self._load_questions()

    def _create_brain(self):
        brain = Brain(name='New Brain')
        self.app.brain_repo.create(brain)
        self._load_brains()
        self._brain_combo.setCurrentIndex(0)

    def _show_brain_edit(self):
        if not self._current_brain:
            return
        self._editing_brain = self._current_brain
        self._brain_name_input.setText(self._editing_brain.name)
        self._brain_desc_input.setText(self._editing_brain.description)
        self._stack.setCurrentIndex(1)

    def _save_brain(self):
        if not self._editing_brain:
            return
        self._editing_brain.name = self._brain_name_input.text().strip() or 'Unnamed Brain'
        self._editing_brain.description = self._brain_desc_input.text().strip()
        self.app.brain_repo.update(self._editing_brain)
        self._load_brains()
        self._stack.setCurrentIndex(0)

    def _delete_brain(self):
        if not self._editing_brain:
            return
        brains = self.app.brain_repo.get_all()
        if len(brains) <= 1:
            QMessageBox.warning(self, 'Cannot Delete', 'You must have at least one brain.')
            return
        self.app.brain_repo.delete(self._editing_brain.id)
        self._editing_brain = None
        self._load_brains()
        self._stack.setCurrentIndex(0)

    def _load_questions(self):
        while self._questions_layout.count() > 1:
            item = self._questions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._current_brain:
            return

        self._questions = self.app.question_repo.get_by_brain(self._current_brain.id)
        for q in self._questions:
            row = QuestionRow(q)
            row.clicked.connect(self._execute_question)
            row.edit_clicked.connect(self._show_question_edit)
            self._questions_layout.insertWidget(self._questions_layout.count() - 1, row)

    def _create_question(self):
        if not self._current_brain:
            return
        q = Question(brain_id=self._current_brain.id, text='New question', position=len(self._questions))
        self.app.question_repo.create(q)
        self._load_questions()

    def _show_question_edit(self, question: Question):
        self._editing_question = question
        self._question_text_input.setText(question.text)
        self._stack.setCurrentIndex(2)

    def _save_question(self):
        if not self._editing_question:
            return
        self._editing_question.text = self._question_text_input.text().strip() or 'Unnamed question'
        self.app.question_repo.update(self._editing_question)
        self._load_questions()
        self._stack.setCurrentIndex(0)

    def _delete_question(self):
        if not self._editing_question:
            return
        self.app.question_repo.delete(self._editing_question.id)
        self._editing_question = None
        self._load_questions()
        self._stack.setCurrentIndex(0)

    def _execute_question(self, question: Question):
        session = self.app.audio_service.get_current_session()
        if not session:
            QMessageBox.warning(self, 'No Session', 'Start a recording session first.')
            return
        self._run_query(question.text, QueryType.PRESET, question.id)

    def start_recording(self):
        session = Session(name='Recording Session')
        self.app.audio_service.start_session(session, self._on_transcript)
        self._clear_transcript_display()
        self._final_transcripts = []
        self._partial_entry = None
        self._recording_seconds = 0
        self._duration_timer.start(1000)
        self._update_live_indicator(True)

    def stop_recording(self):
        self.app.audio_service.stop_session()
        self._duration_timer.stop()
        self._update_live_indicator(False)

    def _update_duration(self):
        self._recording_seconds += 1

    def _update_live_indicator(self, recording: bool):
        if recording:
            self._live_dot.setStyleSheet('color: #ff4444; font-size: 14px;')
            self._live_label.setStyleSheet('color: #ff4444;')
        else:
            self._live_dot.setStyleSheet('color: #666666; font-size: 14px;')
            self._live_label.setStyleSheet('color: #666666;')

    def _on_transcript(self, entry: TranscriptEntry, is_final: bool):
        if is_final:
            self._final_transcripts.append(entry)
            self._partial_entry = None
        else:
            self._partial_entry = entry
        self._update_transcript_display()

    def _clear_transcript_display(self):
        while self._transcript_layout.count():
            item = self._transcript_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _update_transcript_display(self):
        self._clear_transcript_display()

        entries = self._final_transcripts[-6:]
        if self._partial_entry:
            entries = entries + [self._partial_entry]

        for entry in entries:
            arrow = '→' if entry.speaker == SpeakerType.USER else '←'
            label = QLabel(f'{arrow} {entry.text}')
            label.setWordWrap(True)
            if entry.speaker == SpeakerType.USER:
                label.setObjectName('transcriptUser')
            else:
                label.setObjectName('transcriptOther')
            self._transcript_layout.addWidget(label)

    def _ask_brain(self):
        query_text = self._ask_input.text().strip()
        if not query_text:
            return

        session = self.app.audio_service.get_current_session()
        if not session:
            QMessageBox.warning(self, 'No Session', 'Start a recording session first.')
            return

        self._ask_input.clear()
        self._run_query(query_text, QueryType.FREEFORM)

    def _run_query(self, query_text: str, query_type: QueryType, question_id: Optional[str] = None):
        brain = self._current_brain or self.app._default_brain
        if not brain:
            QMessageBox.warning(self, 'Not Ready', 'Please wait for initialization.')
            return

        session = self.app.audio_service.get_current_session()
        if not session:
            return

        self._response.clear()
        self._query_status.setText('')

        self._query_thread = QueryExecutionThread(
            db=self.app.db,
            embedder=self.app.embedder,
            session_id=session.id,
            brain=brain,
            query_text=query_text,
            query_type=query_type,
            question_id=question_id
        )
        self._query_thread.step_update.connect(self._on_step_update)
        self._query_thread.delta.connect(self._on_query_delta)
        self._query_thread.complete.connect(self._on_query_complete)
        self._query_thread.start()

    def _on_step_update(self, step: ExecutionStep):
        labels = {
            StepType.LISTENING: 'Reviewing conversation...',
            StepType.SEARCHING_FILES: 'Searching files...',
            StepType.GENERATING: 'Thinking...'
        }
        label = labels.get(step.step_type, str(step.step_type.value))
        self._query_status.setText(label)

    def _on_query_delta(self, text: str):
        self._response.insertPlainText(text)

    def _on_query_complete(self, _response):
        self._query_status.setText('')
