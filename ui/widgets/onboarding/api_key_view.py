from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit
from PySide6.QtCore import Qt, Signal

from ui.styles import BASE_STYLE, INPUT_STYLE, ACCENT, TEXT_SECONDARY
from services.secrets import secrets


class ApiKeyView(QWidget):
    api_key_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(BASE_STYLE + INPUT_STYLE)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        header = QLabel('Connect to OpenAI')
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet('font-size: 22px; font-weight: 700;')
        layout.addWidget(header)

        desc = QLabel('Paste your API key to power Livebrain')
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 14px;')
        layout.addWidget(desc)

        layout.addSpacing(16)

        self._input = QLineEdit()
        self._input.setPlaceholderText('sk-...')
        self._input.setEchoMode(QLineEdit.EchoMode.Password)
        self._input.setFixedWidth(320)
        self._input.returnPressed.connect(self._submit)
        layout.addWidget(self._input, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        self._btn = QPushButton('Next')
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFixedWidth(200)
        self._btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {ACCENT};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 15px;
                font-weight: 600;
            }}
        ''')
        self._btn.clicked.connect(self._submit)
        layout.addWidget(self._btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _submit(self):
        key = self._input.text().strip()
        if not key:
            return
        secrets.set('openai_api_key', key)
        self.api_key_submitted.emit(key)
