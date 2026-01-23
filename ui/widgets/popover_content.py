from typing import TYPE_CHECKING, Optional
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QLabel, QComboBox, QCheckBox,
    QScrollArea, QFrame, QProgressDialog, QMessageBox,
    QStackedWidget, QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QTimer, Signal

import qtawesome as qta

from models import Session, TranscriptEntry, SpeakerType, QueryType, StepType, ExecutionStep, Brain, Question, Resource, ResourceType, IndexStatus
from services.embedder import Embedder
from ui.threads import ModelDownloadThread, QueryExecutionThread, IndexThread, EstimateThread

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
    color: #5fb85f;
    font-size: 13px;
}
QLabel#transcriptOther {
    color: #ffffff;
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
QComboBox#settingsCombo {
    background-color: #1e1e1e;
    border: 1px solid #3a3a3a;
    border-radius: 8px;
    padding: 8px 12px;
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
    pop_out_requested = Signal()

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
        self._resource_checkboxes: dict[str, QCheckBox] = {}
        self._folder_status_label = None
        self._folder_confirm_widget = None

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
        self._stack.addWidget(self._build_resources_view())
        self._stack.addWidget(self._build_settings_view())

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

        self._pop_out_btn = QPushButton()
        self._pop_out_btn.setObjectName('iconBtn')
        self._pop_out_btn.setIcon(qta.icon('mdi.open-in-new', color='#888888'))
        self._pop_out_btn.setFixedSize(24, 24)
        self._pop_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pop_out_btn.setToolTip('Open in window')
        self._pop_out_btn.clicked.connect(self.pop_out_requested.emit)
        header.addWidget(self._pop_out_btn)

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

        self._settings_btn = QPushButton()
        self._settings_btn.setObjectName('iconBtn')
        self._settings_btn.setIcon(qta.icon('mdi.cog', color='#888888'))
        self._settings_btn.setFixedSize(24, 24)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self._show_settings)
        header.addWidget(self._settings_btn)

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
        layout.setSpacing(12)
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

        # Capabilities toggles
        layout.addWidget(self._section_label('CAPABILITIES'))
        self._conv_toggle = QCheckBox('Use conversation')
        self._files_toggle = QCheckBox('Search linked resources')
        self._web_toggle = QCheckBox('Search the web')
        self._code_toggle = QCheckBox('Run code')
        layout.addWidget(self._conv_toggle)
        layout.addWidget(self._files_toggle)
        layout.addWidget(self._web_toggle)
        layout.addWidget(self._code_toggle)

        # Resource links section
        layout.addWidget(self._section_label('LINKED RESOURCES'))
        self._resource_links_container = QWidget()
        self._resource_links_layout = QVBoxLayout(self._resource_links_container)
        self._resource_links_layout.setContentsMargins(0, 0, 0, 0)
        self._resource_links_layout.setSpacing(4)
        layout.addWidget(self._resource_links_container)

        manage_btn = QPushButton('Manage Resources →')
        manage_btn.clicked.connect(self._show_resources_view)
        layout.addWidget(manage_btn)

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
        caps = self._editing_brain.capabilities
        self._conv_toggle.setChecked(caps.conversation)
        self._files_toggle.setChecked(caps.files)
        self._web_toggle.setChecked(caps.web)
        self._code_toggle.setChecked(caps.code)
        self._load_resource_links()
        self._stack.setCurrentIndex(1)

    def _save_brain(self):
        if not self._editing_brain:
            return
        self._editing_brain.name = self._brain_name_input.text().strip() or 'Unnamed Brain'
        self._editing_brain.description = self._brain_desc_input.text().strip()
        self._editing_brain.capabilities.conversation = self._conv_toggle.isChecked()
        self._editing_brain.capabilities.files = self._files_toggle.isChecked()
        self._editing_brain.capabilities.web = self._web_toggle.isChecked()
        self._editing_brain.capabilities.code = self._code_toggle.isChecked()

        current_links = set(r.id for r in self.app.resource_repo.get_by_brain(self._editing_brain.id))
        new_links = set(rid for rid, cb in self._resource_checkboxes.items() if cb.isChecked())
        for rid in current_links - new_links:
            self.app.resource_repo.unlink_from_brain(rid, self._editing_brain.id)
        for rid in new_links - current_links:
            self.app.resource_repo.link_to_brain(rid, self._editing_brain.id)

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
            arrow = '←' if entry.speaker == SpeakerType.USER else '→'
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
        self._query_status.setText(labels.get(step.step_type, ''))

    def _on_query_delta(self, text: str):
        self._response.insertPlainText(text)

    def _on_query_complete(self, _response):
        self._query_status.setText('')

    def _load_resource_links(self):
        while self._resource_links_layout.count():
            item = self._resource_links_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._resource_checkboxes = {}
        if not self._editing_brain:
            return

        all_resources = self.app.resource_repo.get_all()
        linked = set(r.id for r in self.app.resource_repo.get_by_brain(self._editing_brain.id))

        for resource in all_resources:
            icon = '📄' if resource.resource_type == ResourceType.FILE else '📁'
            size_str = f'{resource.size_mb:.1f} MB' if resource.size_bytes else ''
            label = f'{icon} {resource.name} ({size_str})' if size_str else f'{icon} {resource.name}'
            checkbox = QCheckBox(label)
            checkbox.setChecked(resource.id in linked)
            self._resource_checkboxes[resource.id] = checkbox
            self._resource_links_layout.addWidget(checkbox)

    def _build_resources_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        # Header
        header = QHBoxLayout()
        back_btn = QPushButton()
        back_btn.setObjectName('iconBtn')
        back_btn.setIcon(qta.icon('mdi.arrow-left', color='#6eb5ff'))
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        header.addWidget(back_btn)
        header.addStretch()
        title = QLabel('Resources')
        title.setStyleSheet('font-weight: 600; font-size: 14px; color: #e0e0e0;')
        header.addWidget(title)
        header.addStretch()
        header.addSpacing(28)
        layout.addLayout(header)

        # Files section
        layout.addWidget(self._section_label('FILES'))
        files_desc = QLabel('Images and PDFs sent directly to the AI')
        files_desc.setStyleSheet('color: #666; font-size: 11px; margin-bottom: 4px;')
        layout.addWidget(files_desc)
        self._files_container = QWidget()
        self._files_layout = QVBoxLayout(self._files_container)
        self._files_layout.setContentsMargins(0, 0, 0, 0)
        self._files_layout.setSpacing(4)
        layout.addWidget(self._files_container)

        add_files_btn = QPushButton('Add Files')
        add_files_btn.clicked.connect(self._add_resource_files)
        layout.addWidget(add_files_btn)

        # Folders section
        layout.addWidget(self._section_label('FOLDERS'))
        folders_desc = QLabel('AI can search through these files')
        folders_desc.setStyleSheet('color: #666; font-size: 11px; margin-bottom: 4px;')
        layout.addWidget(folders_desc)
        self._folders_container = QWidget()
        self._folders_layout = QVBoxLayout(self._folders_container)
        self._folders_layout.setContentsMargins(0, 0, 0, 0)
        self._folders_layout.setSpacing(4)
        layout.addWidget(self._folders_container)

        add_folder_btn = QPushButton('Add Folder')
        add_folder_btn.clicked.connect(self._add_resource_folder)
        layout.addWidget(add_folder_btn)

        layout.addStretch()
        return view

    def _build_settings_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        back_btn = QPushButton()
        back_btn.setObjectName('iconBtn')
        back_btn.setIcon(qta.icon('mdi.arrow-left', color='#6eb5ff'))
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        header.addWidget(back_btn)
        header.addStretch()
        title = QLabel('Settings')
        title.setStyleSheet('font-weight: 600; font-size: 14px; color: #e0e0e0;')
        header.addWidget(title)
        header.addStretch()
        header.addSpacing(28)
        layout.addLayout(header)

        layout.addWidget(self._section_label('AI CONNECTION'))
        layout.addWidget(QLabel('AI Key'))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText('Enter your OpenAI API key')
        layout.addWidget(self._api_key_input)

        self._api_key_status = QLabel()
        self._api_key_status.setStyleSheet('font-size: 11px;')
        layout.addWidget(self._api_key_status)

        layout.addWidget(self._section_label('MODEL'))
        layout.addWidget(QLabel('AI Model'))
        self._model_combo = QComboBox()
        self._model_combo.setObjectName('settingsCombo')
        self._model_combo.addItem('GPT-5', 'gpt-5-chat-latest')
        self._model_combo.addItem('GPT-4.1', 'gpt-4.1')
        self._model_combo.addItem('GPT-4.1 Mini', 'gpt-4.1-mini')
        self._model_combo.addItem('GPT-4o', 'gpt-4o')
        layout.addWidget(self._model_combo)

        layout.addStretch()

        save_btn = QPushButton('Save')
        save_btn.setStyleSheet('background-color: #2d4a2d; border-color: #3a5a3a;')
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        return view

    def _show_settings(self):
        settings = self.app.settings_repo.get()
        from services.secrets import secrets
        api_key = secrets.get('openai_api_key')
        self._api_key_input.setText(api_key or '')
        self._update_api_key_status(api_key)

        for i in range(self._model_combo.count()):
            if self._model_combo.itemData(i) == settings.preferred_model:
                self._model_combo.setCurrentIndex(i)
                break

        self._stack.setCurrentIndex(4)

    def _save_settings(self):
        from services.secrets import secrets
        api_key = self._api_key_input.text().strip()
        if api_key:
            secrets.set('openai_api_key', api_key)
        else:
            secrets.delete('openai_api_key')

        settings = self.app.settings_repo.get()
        settings.preferred_model = self._model_combo.currentData()
        self.app.settings_repo.update(settings)
        self._stack.setCurrentIndex(0)

    def _update_api_key_status(self, key: Optional[str]):
        if key:
            self._api_key_status.setText('Set')
            self._api_key_status.setStyleSheet('color: #4CAF50; font-size: 11px;')
        else:
            self._api_key_status.setText('Not set')
            self._api_key_status.setStyleSheet('color: #ff6b6b; font-size: 11px;')

    def _show_resources_view(self):
        self._load_resources()
        self._stack.setCurrentIndex(3)

    def _add_resource_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Select Files',
            filter='Images & PDFs (*.png *.jpg *.jpeg *.gif *.webp *.pdf)'
        )
        for filepath in files:
            resource = Resource(
                resource_type=ResourceType.FILE,
                name=os.path.basename(filepath),
                path=filepath,
                size_bytes=os.path.getsize(filepath),
                file_count=1,
                index_status=IndexStatus.INDEXED
            )
            self.app.resource_repo.create(resource)
        self._load_resources()

    def _add_resource_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if not folder:
            return

        self._pending_folder_path = folder
        self._pending_folder_name = os.path.basename(folder)

        # Show scanning status inline
        self._show_folder_status(f'Scanning {self._pending_folder_name}...')

        # Run estimation first
        self._estimate_thread = EstimateThread(folder, self.app.scanner)
        self._estimate_thread.complete.connect(self._on_estimation_complete)
        self._estimate_thread.start()

    def _show_folder_status(self, text: str, is_processing: bool = False):
        self._clear_folder_status()
        self._folder_status_label = QLabel(text)
        color = '#6eb5ff' if is_processing else '#888'
        self._folder_status_label.setStyleSheet(f'color: {color}; font-size: 12px; padding: 8px;')
        self._folders_layout.addWidget(self._folder_status_label)

    def _clear_folder_status(self):
        if self._folder_status_label:
            self._folder_status_label.deleteLater()
            self._folder_status_label = None
        if self._folder_confirm_widget:
            self._folder_confirm_widget.deleteLater()
            self._folder_confirm_widget = None

    def _on_estimation_complete(self, total_bytes: int, file_count: int, paths: list):
        self._clear_folder_status()
        self._pending_paths = paths
        self._pending_bytes = total_bytes
        self._pending_file_count = file_count

        size_mb = total_bytes / (1024 * 1024)
        is_large = total_bytes > 100 * 1024 * 1024

        # Show inline confirmation
        self._folder_confirm_widget = QWidget()
        layout = QVBoxLayout(self._folder_confirm_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        info_text = f'{self._pending_folder_name}: {file_count} files ({size_mb:.1f} MB)'
        if is_large:
            info_text += '\n⚠️ This may take a while'
        info_label = QLabel(info_text)
        info_label.setStyleSheet('color: #d0d0d0;')
        layout.addWidget(info_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        add_btn = QPushButton('Add')
        add_btn.setStyleSheet('background-color: #2d4a2d; border-color: #3a5a3a;')
        add_btn.clicked.connect(self._confirm_folder_index)
        btn_row.addWidget(add_btn)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self._cancel_folder_index)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._folders_layout.addWidget(self._folder_confirm_widget)

    def _confirm_folder_index(self):
        self._clear_folder_status()

        # Create resource now that user confirmed
        resource = Resource(
            resource_type=ResourceType.FOLDER,
            name=self._pending_folder_name,
            path=self._pending_folder_path,
            index_status=IndexStatus.INDEXING
        )
        self.app.resource_repo.create(resource)
        self._current_indexing_resource = resource

        # Show progress inline
        self._show_folder_status(f'Processing 0/{self._pending_file_count}...', is_processing=True)

        # Start actual indexing
        self._index_thread = IndexThread(
            resource=resource,
            paths=self._pending_paths,
            embedder=self.app.embedder,
            scanner=self.app.scanner,
            rag=self.app.rag
        )
        self._index_thread.file_progress.connect(self._on_file_progress)
        self._index_thread.complete.connect(self._on_indexing_complete)
        self._index_thread.start()

    def _cancel_folder_index(self):
        self._clear_folder_status()
        self._load_resources()

    def _on_file_progress(self, filename: str, current: int, total: int):
        if self._folder_status_label:
            self._folder_status_label.setText(f'Processing {current}/{total}: {filename}')

    def _on_indexing_complete(self, total_bytes: int, file_count: int):
        self._clear_folder_status()
        self.app.resource_repo.update_index_status(
            self._current_indexing_resource.id, IndexStatus.INDEXED,
            size_bytes=total_bytes, file_count=file_count
        )
        self._load_resources()

    def _load_resources(self):
        # Load files
        while self._files_layout.count():
            item = self._files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Load folders
        while self._folders_layout.count():
            item = self._folders_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_resources = self.app.resource_repo.get_all()

        for resource in all_resources:
            row = QHBoxLayout()
            icon_name = 'mdi.file' if resource.resource_type == ResourceType.FILE else 'mdi.folder'
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon(icon_name, color='#888').pixmap(16, 16))
            row.addWidget(icon_label)

            name_label = QLabel(resource.name)
            name_label.setStyleSheet('color: #d0d0d0;')
            row.addWidget(name_label)

            if resource.size_bytes:
                size_label = QLabel(f'{resource.size_mb:.1f} MB')
                size_label.setStyleSheet('color: #666; font-size: 11px;')
                row.addWidget(size_label)

            if resource.resource_type == ResourceType.FOLDER:
                if resource.file_count:
                    count_label = QLabel(f'{resource.file_count} files')
                    count_label.setStyleSheet('color: #666; font-size: 11px;')
                    row.addWidget(count_label)

                status_map = {
                    IndexStatus.PENDING: 'Waiting...',
                    IndexStatus.INDEXING: 'Processing...',
                    IndexStatus.INDEXED: 'Ready',
                    IndexStatus.FAILED: 'Failed'
                }
                status_text = status_map.get(resource.index_status, resource.index_status.value)
                status_color = '#4CAF50' if resource.index_status == IndexStatus.INDEXED else '#666'
                status_label = QLabel(status_text)
                status_label.setStyleSheet(f'color: {status_color}; font-size: 11px;')
                row.addWidget(status_label)

            delete_btn = QPushButton()
            delete_btn.setObjectName('iconBtn')
            delete_btn.setIcon(qta.icon('mdi.close', color='#666'))
            delete_btn.setFixedSize(20, 20)
            delete_btn.clicked.connect(lambda checked, r=resource: self._delete_resource(r))
            row.addWidget(delete_btn)
            row.addStretch()

            container = QWidget()
            container.setLayout(row)

            if resource.resource_type == ResourceType.FILE:
                self._files_layout.addWidget(container)
            else:
                self._folders_layout.addWidget(container)

    def _delete_resource(self, resource: Resource):
        self.app.rag.delete_resource(resource.id)
        self._load_resources()
        self._load_resource_links()

    def set_detached(self, detached: bool):
        if detached:
            self._pop_out_btn.setIcon(qta.icon('mdi.arrow-collapse', color='#888888'))
            self._pop_out_btn.setToolTip('Back to menu bar')
        else:
            self._pop_out_btn.setIcon(qta.icon('mdi.open-in-new', color='#888888'))
            self._pop_out_btn.setToolTip('Open in window')
