import sys

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QTimer

from ui.styles import BASE_STYLE, INPUT_STYLE, ACCENT, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM, FONT_FAMILY
from services import permissions
from services.secrets import secrets


class CheckRow(QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(10)

        self._icon = QLabel()
        self._icon.setFixedSize(20, 20)
        self._layout.addWidget(self._icon)

        self._label = QLabel(label)
        self._label.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 14px;')
        self._layout.addWidget(self._label, 1)

        self._action_btn = QPushButton()
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setFixedHeight(28)
        self._action_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {ACCENT};
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
                color: white;
            }}
        ''')
        self._action_btn.setVisible(False)
        self._layout.addWidget(self._action_btn)

        self._input = None
        self.set_status(False)

    def set_status(self, ok):
        if ok:
            self._icon.setPixmap(qta.icon('mdi.check-circle', color=ACCENT).pixmap(20, 20))
            self._action_btn.setVisible(False)
            if self._input:
                self._input.setVisible(False)
                self._save_btn.setVisible(False)
        else:
            self._icon.setPixmap(qta.icon('mdi.circle-outline', color=TEXT_DIM).pixmap(20, 20))
            if self._action_btn.text():
                self._action_btn.setVisible(True)

    def set_action(self, text, callback):
        self._action_btn.setText(text)
        self._action_btn.setVisible(True)
        self._action_btn.clicked.connect(callback)

    def add_input(self, placeholder, on_submit):
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setEchoMode(QLineEdit.EchoMode.Password)
        self._input.setFixedWidth(200)
        self._input.setStyleSheet(INPUT_STYLE)
        self._input.setVisible(False)
        self._input.returnPressed.connect(lambda: on_submit(self._input.text().strip()))

        self._save_btn = QPushButton('Save')
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setFixedHeight(28)
        self._save_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {ACCENT};
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
        ''')
        self._save_btn.setVisible(False)
        self._save_btn.clicked.connect(lambda: on_submit(self._input.text().strip()))

        self._layout.addWidget(self._input)
        self._layout.addWidget(self._save_btn)

    def show_input(self):
        self._action_btn.setVisible(False)
        if self._input:
            self._input.setVisible(True)
            self._save_btn.setVisible(True)
            self._input.setFocus()


class SetupView(QWidget):
    setup_complete = Signal()
    _recheck = Signal()
    _screen_result = Signal(bool)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app
        self._is_linux = sys.platform != 'darwin'
        self.setStyleSheet(BASE_STYLE + INPUT_STYLE)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        brain_icon = QLabel()
        brain_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brain_icon.setPixmap(qta.icon('mdi.brain', color=ACCENT).pixmap(48, 48))
        layout.addWidget(brain_icon)

        title = QLabel('Livebrain')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'font-size: 28px; font-weight: 700; font-family: {FONT_FAMILY};')
        layout.addWidget(title)

        subtitle = QLabel("Let's get everything ready")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 14px;')
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        self._mic_row = CheckRow('Microphone access')
        self._screen_row = CheckRow('Screen recording')
        self._model_row = CheckRow('AI model')
        self._key_row = CheckRow('OpenAI API key')

        if self._is_linux:
            for row in [self._model_row, self._key_row]:
                layout.addWidget(row)
        else:
            for row in [self._mic_row, self._screen_row, self._model_row, self._key_row]:
                layout.addWidget(row)

        layout.addSpacing(16)

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(f'color: {ACCENT}; font-size: 14px; font-weight: 600;')
        layout.addWidget(self._status_label)

        self._mic_row.set_action('Grant Access', self._request_mic)
        self._screen_row.set_action('Grant Access', self._request_screen)
        self._model_row.set_action('Download', self._download_model)
        self._key_row.set_action('Enter Key', self._show_key_input)
        self._key_row.add_input('sk-...', self._save_key)

        self._recheck.connect(self.run_checks)
        self._screen_result.connect(self._on_screen_result)

    def run_checks(self):
        mic = permissions.check_microphone()
        model = permissions.check_model_downloaded()
        vosk = permissions.check_vosk_model_downloaded()
        key = permissions.check_api_key()

        self._mic_row.set_status(mic)
        self._model_row.set_status(model and vosk)
        self._key_row.set_status(key)

        self._pending_checks = (mic, model and vosk, key)
        permissions.check_screen_recording(self._on_screen_check)

    def _on_screen_check(self, ok):
        self._screen_result.emit(ok)

    def _on_screen_result(self, screen_ok):
        mic, model, key = self._pending_checks
        self._screen_row.set_status(screen_ok)
        if all([screen_ok, model, key]):
            self._status_label.setText('All set!')
            QTimer.singleShot(800, self.setup_complete.emit)
        else:
            self._status_label.setText('')

    def _request_mic(self):
        permissions.request_microphone(lambda _: self._recheck.emit())
        self._start_recheck_poll()

    def _request_screen(self):
        permissions.request_screen_recording(lambda _: self._recheck.emit())
        self._start_recheck_poll()

    def _start_recheck_poll(self):
        if hasattr(self, '_poll_timer') and self._poll_timer.isActive():
            return
        self._poll_timer = QTimer(self)
        self._poll_count = 0
        def poll():
            self._poll_count += 1
            self.run_checks()
            if self._poll_count >= 30:
                self._poll_timer.stop()
        self._poll_timer.timeout.connect(poll)
        self._poll_timer.start(2000)

    def _download_model(self):
        from ui.threads.model_download_thread import ModelDownloadThread
        from services.embedder import Embedder
        self._model_row._action_btn.setVisible(False)

        def on_progress(pct, downloaded, total):
            self._model_row._label.setText(f'AI model \u2014 downloading {pct}%')

        def on_complete(success, msg):
            if success:
                self._app._init_embedder()
                if self._is_linux:
                    self._download_vosk()
                    return
            self._model_row._label.setText('AI model')
            self.run_checks()

        self._download_thread = ModelDownloadThread(self._app.updater, Embedder.get_model_dir())
        self._download_thread.progress.connect(on_progress)
        self._download_thread.finished.connect(on_complete)
        self._download_thread.start()

    def _download_vosk(self):
        from ui.threads.model_download_thread import ModelDownloadThread
        from audio.transcription.vosk_transcriber import _model_dir
        import os

        if os.path.isdir(_model_dir()):
            self._model_row._label.setText('AI model')
            self.run_checks()
            return

        def on_progress(pct, downloaded, total):
            self._model_row._label.setText(f'Speech model \u2014 downloading {pct}%')

        def on_complete(success, msg):
            self._model_row._label.setText('AI model')
            self.run_checks()

        models_parent = os.path.dirname(_model_dir())
        self._vosk_thread = ModelDownloadThread(
            self._app.updater, models_parent,
            download_fn=self._app.updater.download_vosk_model
        )
        self._vosk_thread.progress.connect(on_progress)
        self._vosk_thread.finished.connect(on_complete)
        self._vosk_thread.start()

    def _show_key_input(self):
        self._key_row.show_input()

    def _save_key(self, key):
        secrets.set('openai_api_key', key)
        self.run_checks()
