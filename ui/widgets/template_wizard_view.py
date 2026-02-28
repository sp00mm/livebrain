from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QLineEdit, QFileDialog, QStackedWidget
)
from PySide6.QtCore import Qt, Signal

from services.scanner import FileScanner
from services.template_service import TemplateService
from templates import TEMPLATES
from ui.styles import STYLE_SHEET, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_BG, ACCENT_BORDER
from ui.threads import UrlScrapeThread


class TemplateWizardView(QWidget):
    brain_created = Signal(str)
    navigate_back = Signal()

    def __init__(self, template_service: TemplateService):
        super().__init__()
        self._service = template_service
        self._scanner = FileScanner()
        self._template_key = None
        self._steps = []
        self._current_step = 0
        self._step_values = {}
        self._scrape_thread = None

        self.setStyleSheet(STYLE_SHEET)
        self._setup_ui()

    def load_template(self, template_key: str):
        self._template_key = template_key
        self._steps = TEMPLATES[template_key].steps
        self._current_step = 0
        self._step_values = {}
        self._render_step()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        self._back_btn = QPushButton('← Back')
        self._back_btn.setStyleSheet(f'border: none; color: #6eb5ff; background: transparent;')
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self._go_back)
        header.addWidget(self._back_btn)
        header.addStretch()
        self._step_label = QLabel()
        self._step_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        header.addWidget(self._step_label)
        layout.addLayout(header)

        self._title = QLabel()
        self._title.setStyleSheet(f'font-weight: 600; font-size: 15px; color: {TEXT_PRIMARY};')
        layout.addWidget(self._title)

        self._description = QLabel()
        self._description.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        self._description.setWordWrap(True)
        layout.addWidget(self._description)

        self._content_stack = QStackedWidget()
        layout.addWidget(self._content_stack, 1)

        self._text_page = self._build_text_page()
        self._folder_page = self._build_folder_page()
        self._url_page = self._build_url_page()
        self._content_stack.addWidget(self._text_page)
        self._content_stack.addWidget(self._folder_page)
        self._content_stack.addWidget(self._url_page)

        footer = QHBoxLayout()
        self._skip_btn = QPushButton('Skip')
        self._skip_btn.clicked.connect(self._skip_step)
        footer.addWidget(self._skip_btn)
        footer.addStretch()
        self._next_btn = QPushButton('Next')
        self._next_btn.setStyleSheet(f'background-color: {ACCENT_BG}; border-color: {ACCENT_BORDER};')
        self._next_btn.clicked.connect(self._next_step)
        footer.addWidget(self._next_btn)
        layout.addLayout(footer)

    def _build_text_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText('Type or paste content here...')
        layout.addWidget(self._text_edit, 1)

        self._upload_btn = QPushButton('Upload PDF')
        self._upload_btn.clicked.connect(self._upload_pdf)
        layout.addWidget(self._upload_btn)

        return page

    def _build_folder_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        self._folder_btn = QPushButton('Select Folder')
        self._folder_btn.clicked.connect(self._select_folder)
        layout.addWidget(self._folder_btn)

        self._folder_path_label = QLabel('')
        self._folder_path_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        self._folder_path_label.setWordWrap(True)
        layout.addWidget(self._folder_path_label)

        layout.addStretch()
        return page

    def _build_url_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self._url_text_edit = QTextEdit()
        self._url_text_edit.setPlaceholderText('Type or paste content here...')
        layout.addWidget(self._url_text_edit, 1)

        self._url_link = QPushButton('Generate from URL')
        self._url_link.setStyleSheet(f'border: none; color: #6eb5ff; background: transparent; text-align: left;')
        self._url_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._url_link.clicked.connect(self._toggle_url_input)
        layout.addWidget(self._url_link)

        self._url_input_row = QWidget()
        row_layout = QHBoxLayout(self._url_input_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText('https://...')
        row_layout.addWidget(self._url_input, 1)
        self._generate_btn = QPushButton('Generate')
        self._generate_btn.setStyleSheet(f'background-color: {ACCENT_BG}; border-color: {ACCENT_BORDER};')
        self._generate_btn.clicked.connect(self._generate_from_url)
        row_layout.addWidget(self._generate_btn)
        self._url_input_row.setVisible(False)
        layout.addWidget(self._url_input_row)

        self._url_status = QLabel('')
        self._url_status.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px; font-style: italic;')
        layout.addWidget(self._url_status)

        return page

    def _render_step(self):
        step = self._steps[self._current_step]
        self._step_label.setText(f'Step {self._current_step + 1} of {len(self._steps)}')
        self._title.setText(step.label)
        self._description.setText(step.description)

        is_last = self._current_step == len(self._steps) - 1
        self._next_btn.setText('Create' if is_last else 'Next')

        if step.input_type == 'text':
            self._text_edit.clear()
            self._text_edit.setPlainText(self._step_values.get(step.key, ''))
            self._content_stack.setCurrentIndex(0)
        elif step.input_type == 'folder':
            path = self._step_values.get(step.key, '')
            self._folder_path_label.setText(path)
            self._content_stack.setCurrentIndex(1)
        elif step.input_type == 'text_with_url':
            self._url_text_edit.clear()
            self._url_text_edit.setPlainText(self._step_values.get(step.key, ''))
            self._url_input_row.setVisible(False)
            self._url_input.clear()
            self._url_status.clear()
            self._content_stack.setCurrentIndex(2)

    def _go_back(self):
        if self._current_step > 0:
            self._save_current_value()
            self._current_step -= 1
            self._render_step()
        else:
            self.navigate_back.emit()

    def _skip_step(self):
        if self._current_step < len(self._steps) - 1:
            self._current_step += 1
            self._render_step()
        else:
            self._create_brain()

    def _next_step(self):
        self._save_current_value()
        if self._current_step < len(self._steps) - 1:
            self._current_step += 1
            self._render_step()
        else:
            self._create_brain()

    def _save_current_value(self):
        step = self._steps[self._current_step]
        if step.input_type == 'text':
            value = self._text_edit.toPlainText().strip()
        elif step.input_type == 'folder':
            value = self._folder_path_label.text()
        elif step.input_type == 'text_with_url':
            value = self._url_text_edit.toPlainText().strip()
        else:
            value = ''
        if value:
            self._step_values[step.key] = value

    def _create_brain(self):
        brain = self._service.create_brain_from_template(self._template_key, self._step_values)
        self.brain_created.emit(brain.id)

    def _upload_pdf(self):
        filepath, _ = QFileDialog.getOpenFileName(self, 'Select PDF', filter='PDF Files (*.pdf)')
        if filepath:
            text = self._scanner.extract_text(filepath)
            if text:
                self._text_edit.setPlainText(text)

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if folder:
            self._folder_path_label.setText(folder)

    def _toggle_url_input(self):
        self._url_input_row.setVisible(not self._url_input_row.isVisible())

    def _generate_from_url(self):
        url = self._url_input.text().strip()
        if not url:
            return
        self._generate_btn.setEnabled(False)
        self._url_status.setText('Generating...')
        self._scrape_thread = UrlScrapeThread(url, self._service)
        self._scrape_thread.complete.connect(self._on_url_complete)
        self._scrape_thread.error.connect(self._on_url_error)
        self._scrape_thread.start()

    def _on_url_complete(self, text: str):
        self._url_text_edit.setPlainText(text)
        self._url_status.clear()
        self._generate_btn.setEnabled(True)

    def _on_url_error(self, error: str):
        self._url_status.setText(f'Failed: {error}')
        self._generate_btn.setEnabled(True)
