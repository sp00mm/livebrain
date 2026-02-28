from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox
)
from PySide6.QtCore import Signal

from services.database import Database, UserSettingsRepository
from services.secrets import secrets
from ui.styles import (
    STYLE_SHEET, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT, FONT_SIZE
)


class SettingsView(QWidget):
    navigate_back = Signal()

    def __init__(self, db: Database):
        super().__init__()
        self.settings_repo = UserSettingsRepository(db)
        self.setStyleSheet(STYLE_SHEET)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(16)

        header = QHBoxLayout()
        back_btn = QPushButton('\u2190 Back')
        back_btn.clicked.connect(self.navigate_back.emit)
        header.addWidget(back_btn)
        title = QLabel('Settings')
        title.setStyleSheet(f'font-size: 16px; font-weight: 600; color: {TEXT_PRIMARY};')
        header.addWidget(title, 1)
        layout.addLayout(header)

        api_label = QLabel('OpenAI API Key')
        api_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        layout.addWidget(api_label)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText('sk-...')
        self._key_input.setObjectName('settingsInput')
        key_row.addWidget(self._key_input, 1)
        self._key_status = QLabel()
        self._key_status.setStyleSheet(f'color: {ACCENT}; font-size: {FONT_SIZE};')
        key_row.addWidget(self._key_status)
        layout.addLayout(key_row)

        mic_label = QLabel('Microphone')
        mic_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        layout.addWidget(mic_label)

        self._mic_combo = QComboBox()
        self._mic_combo.setObjectName('settingsCombo')
        self._mic_combo.addItem('System Default')
        layout.addWidget(self._mic_combo)

        layout.addStretch()

        save_btn = QPushButton('Save')
        save_btn.setObjectName('downloadBtn')
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _load(self):
        existing_key = secrets.get('openai_api_key')
        if existing_key:
            self._key_status.setText('\u2713 Set')
        else:
            self._key_status.setText('')

        settings = self.settings_repo.get()
        if settings.default_input_device:
            idx = self._mic_combo.findText(settings.default_input_device)
            if idx >= 0:
                self._mic_combo.setCurrentIndex(idx)

    def _save(self):
        key_text = self._key_input.text().strip()
        if key_text:
            secrets.set('openai_api_key', key_text)
            self._key_input.clear()
            self._key_status.setText('\u2713 Set')

        settings = self.settings_repo.get()
        device = self._mic_combo.currentText()
        settings.default_input_device = device if device != 'System Default' else None
        self.settings_repo.update(settings)
