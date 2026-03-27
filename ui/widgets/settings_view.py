from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QComboBox, QFrame, QCheckBox
)
from PySide6.QtCore import Signal

from audio.devices import list_input_devices, list_output_devices
from services.database import Database, UserSettingsRepository
from services.secrets import secrets
from services.updater import get_version
from ui.styles import (
    STYLE_SHEET, TEXT_PRIMARY, TEXT_SECONDARY, ACCENT,
    ACCENT_BORDER, FONT_SIZE, BG_CARD
)
from ui.threads import UpdateDownloadThread


class SettingsView(QWidget):
    navigate_back = Signal()

    def __init__(self, db: Database, updater=None):
        super().__init__()
        self.settings_repo = UserSettingsRepository(db)
        self._updater = updater
        self._update_info = None
        self._download_thread = None
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

        devices_label = QLabel('Audio Devices')
        devices_label.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600;')
        layout.addWidget(devices_label)

        mic_label = QLabel('Input Device (Microphone)')
        mic_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        layout.addWidget(mic_label)

        self._mic_combo = QComboBox()
        self._mic_combo.setObjectName('settingsCombo')
        self._mic_combo.addItem('System Default', userData=None)
        for dev in list_input_devices():
            self._mic_combo.addItem(dev.name, userData=dev.id)
        layout.addWidget(self._mic_combo)

        output_devices = list_output_devices()
        if output_devices:
            out_label = QLabel('Output Device (System Audio Source)')
            out_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
            layout.addWidget(out_label)

            self._output_combo = QComboBox()
            self._output_combo.setObjectName('settingsCombo')
            self._output_combo.addItem('System Default', userData=None)
            for dev in output_devices:
                self._output_combo.addItem(dev.name, userData=dev.id)
            layout.addWidget(self._output_combo)
        else:
            self._output_combo = None

        self._feedback_check = QCheckBox('Help improve Livebrain')
        self._feedback_check.setStyleSheet(f'color: {TEXT_PRIMARY};')
        layout.addWidget(self._feedback_check)

        feedback_desc = QLabel(
            'When enabled, you\'ll be asked to rate sessions. '
            'Rated sessions may have anonymized data sent to help '
            'improve the product. No audio or files are ever shared.'
        )
        feedback_desc.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
        feedback_desc.setWordWrap(True)
        layout.addWidget(feedback_desc)

        self._update_card = QFrame()
        self._update_card.setStyleSheet(
            f'QFrame {{ background-color: {BG_CARD}; border: 1px solid {ACCENT_BORDER}; border-radius: 8px; }}'
        )
        self._update_card.setVisible(False)
        update_layout = QVBoxLayout(self._update_card)
        update_layout.setContentsMargins(12, 10, 12, 10)
        update_layout.setSpacing(6)

        self._update_title = QLabel()
        self._update_title.setStyleSheet(f'color: {ACCENT}; font-weight: 600; font-size: {FONT_SIZE}; border: none;')
        update_layout.addWidget(self._update_title)

        self._update_notes = QLabel()
        self._update_notes.setWordWrap(True)
        self._update_notes.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px; border: none;')
        update_layout.addWidget(self._update_notes)

        self._update_btn = QPushButton('Download Update')
        self._update_btn.setObjectName('downloadBtn')
        self._update_btn.clicked.connect(self._download_update)
        update_layout.addWidget(self._update_btn)

        layout.addWidget(self._update_card)

        version_label = QLabel(f'v{get_version()}')
        version_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
        layout.addWidget(version_label)

        layout.addStretch()

        save_btn = QPushButton('Save')
        save_btn.setObjectName('primaryBtn')
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
            for i in range(self._mic_combo.count()):
                if self._mic_combo.itemData(i) == settings.default_input_device:
                    self._mic_combo.setCurrentIndex(i)
                    break

        if self._output_combo and settings.default_output_device:
            for i in range(self._output_combo.count()):
                if self._output_combo.itemData(i) == settings.default_output_device:
                    self._output_combo.setCurrentIndex(i)
                    break

        self._feedback_check.setChecked(settings.feedback_opt_in is True)

    def _save(self):
        key_text = self._key_input.text().strip()
        if key_text:
            secrets.set('openai_api_key', key_text)
            self._key_input.clear()
            self._key_status.setText('\u2713 Set')

        settings = self.settings_repo.get()
        settings.default_input_device = self._mic_combo.currentData()
        if self._output_combo:
            settings.default_output_device = self._output_combo.currentData()
        settings.feedback_opt_in = self._feedback_check.isChecked()
        self.settings_repo.update(settings)

    def show_update(self, info: dict):
        self._update_info = info
        self._update_title.setText(f'Update Available — v{info["version"]}')
        self._update_notes.setText(info.get('notes', ''))
        self._update_btn.setText('Download Update')
        self._update_btn.setEnabled(True)
        self._update_card.setVisible(True)

    def _download_update(self):
        if self._update_info.get('_downloaded_path'):
            self._updater.open_update(self._update_info['_downloaded_path'])
            return

        self._update_btn.setText('Downloading...')
        self._update_btn.setEnabled(False)
        self._download_thread = UpdateDownloadThread(self._updater, self._update_info['url'])
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.start()

    def _on_download_finished(self, path: str):
        self._update_info['_downloaded_path'] = path
        self._update_btn.setText('Open to Install')
        self._update_btn.setEnabled(True)
