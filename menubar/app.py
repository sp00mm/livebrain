import os
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QObject, Signal

from AppKit import NSApp

from services.embedder import Embedder
from services.scanner import FileScanner
from services.database import Database, RAGService, UserSettingsRepository, BrainRepository, QuestionRepository, ResourceRepository
from services.updater import Updater
from services.audio_service import AudioService
from models import Brain

from .status_bar import StatusBarController
from .hotkeys import GlobalHotkeyManager
from .popover_window import PopoverWindow


class RecordingSignals(QObject):
    toggle_requested = Signal()


class MenuBarApp:
    def __init__(self):
        self._init_services()
        self._init_ui()

    def _init_services(self):
        self.scanner = FileScanner()
        self.db = Database()
        self.db.initialize_schema()
        self.rag = RAGService(self.db)
        self.settings_repo = UserSettingsRepository(self.db)
        self.brain_repo = BrainRepository(self.db)
        self.question_repo = QuestionRepository(self.db)
        self.resource_repo = ResourceRepository(self.db)
        self.updater = Updater()
        self.audio_service = AudioService(self.db)
        self.embedder: Optional[Embedder] = None
        self._default_brain: Optional[Brain] = None

        self._init_embedder()

    def _init_embedder(self):
        model_dir = Embedder.get_model_dir()
        model_file = os.path.join(model_dir, 'onnx', 'model_q4.onnx')

        if os.path.exists(model_file):
            self.embedder = Embedder()
            brains = self.brain_repo.get_all()
            if brains:
                self._default_brain = brains[0]
            else:
                self._default_brain = self.brain_repo.create(Brain(name='Default'))

    def _init_ui(self):
        self._signals = RecordingSignals()
        self._signals.toggle_requested.connect(self._toggle_recording)

        from ui.widgets.popover_content import PopoverContent
        self._content = PopoverContent(self)
        self._popover = PopoverWindow(self._content)

        self._status_bar = StatusBarController(
            on_click=self._on_status_click,
            on_quit=self._quit
        )

        self._hotkeys = GlobalHotkeyManager(
            on_toggle_recording=self._on_hotkey_toggle
        )
        self._hotkeys.start()

        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._animate_icon)
        self._animation_state = False

    def _on_status_click(self):
        frame = self._status_bar.get_button_frame()
        self._popover.toggle(frame)

    def _on_hotkey_toggle(self):
        self._signals.toggle_requested.emit()

    def _toggle_recording(self):
        if self.audio_service.is_recording():
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._content.start_recording()
        self._status_bar.set_recording(True)
        self._animation_timer.start(500)

    def _stop_recording(self):
        self._content.stop_recording()
        self._status_bar.set_recording(False)
        self._animation_timer.stop()

    def _animate_icon(self):
        self._animation_state = not self._animation_state
        self._status_bar.set_recording(self._animation_state)

    def _quit(self):
        self._hotkeys.stop()
        if self.audio_service.is_recording():
            self.audio_service.stop_session()
        NSApp.terminate_(None)

    def show_popover(self):
        frame = self._status_bar.get_button_frame()
        self._popover.position_below_status_item(frame)
        self._popover.show()
