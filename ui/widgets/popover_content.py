from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Signal

from services.database import UserSettingsRepository
from ui.styles import STYLE_SHEET

from .live_view import LiveView
from .brain_edit_view import BrainEditView
from .settings_view import SettingsView
from .template_wizard_view import TemplateWizardView
from .onboarding import WelcomeView, ApiKeyView, TemplatePickerView
from .session_history_view import SessionHistoryView

if TYPE_CHECKING:
    from menubar.app import MenuBarApp

LIVE = 0
PICKER = 1
WIZARD = 2
BRAIN_EDIT = 3
SETTINGS = 4
WELCOME = 5
API_KEY = 6
SESSION_HISTORY = 7


class PopoverContent(QWidget):
    pop_out_requested = Signal()

    def __init__(self, app: 'MenuBarApp'):
        super().__init__()
        self._app = app
        self.setStyleSheet(STYLE_SHEET)

        self._stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._live_view = LiveView(app)
        self._picker_view = TemplatePickerView()
        self._wizard_view = TemplateWizardView(app.template_service)
        self._brain_edit_view = BrainEditView(app.db)
        self._settings_view = SettingsView(app.db)
        self._welcome_view = WelcomeView()
        self._api_key_view = ApiKeyView()
        self._session_history_view = SessionHistoryView(app.db)

        self._stack.addWidget(self._live_view)       # 0
        self._stack.addWidget(self._picker_view)     # 1
        self._stack.addWidget(self._wizard_view)     # 2
        self._stack.addWidget(self._brain_edit_view) # 3
        self._stack.addWidget(self._settings_view)   # 4
        self._stack.addWidget(self._welcome_view)    # 5
        self._stack.addWidget(self._api_key_view)    # 6
        self._stack.addWidget(self._session_history_view)  # 7

        self._wire_navigation()
        self._set_starting_view()

    def _wire_navigation(self):
        self._live_view.navigate_to_picker.connect(lambda: self._stack.setCurrentIndex(PICKER))
        self._live_view.navigate_to_brain_edit.connect(self._show_brain_edit)
        self._live_view.navigate_to_settings.connect(lambda: self._stack.setCurrentIndex(SETTINGS))
        self._live_view.pop_out_requested.connect(self.pop_out_requested)

        self._picker_view.template_selected.connect(self._show_wizard)
        self._picker_view.custom_selected.connect(self._show_new_brain)
        self._picker_view.navigate_back.connect(lambda: self._stack.setCurrentIndex(LIVE))

        self._wizard_view.brain_created.connect(self._on_brain_created)
        self._wizard_view.navigate_back.connect(lambda: self._stack.setCurrentIndex(PICKER))

        self._brain_edit_view.navigate_back.connect(self._return_to_live)
        self._brain_edit_view.brain_saved.connect(self._on_brain_saved)
        self._brain_edit_view.brain_deleted.connect(self._on_brain_deleted)

        self._settings_view.navigate_back.connect(lambda: self._stack.setCurrentIndex(LIVE))

        self._live_view.navigate_to_history.connect(self._show_session_history)
        self._session_history_view.navigate_back.connect(lambda: self._stack.setCurrentIndex(LIVE))

        self._welcome_view.next_clicked.connect(lambda: self._stack.setCurrentIndex(API_KEY))
        self._api_key_view.api_key_submitted.connect(self._on_api_key_submitted)

    def _set_starting_view(self):
        settings = UserSettingsRepository(self._app.db).get()
        if settings.onboarding_complete:
            self._stack.setCurrentIndex(LIVE)
        else:
            self._stack.setCurrentIndex(WELCOME)

    def _show_session_history(self):
        if self._live_view._active_brain:
            self._session_history_view.load_brain(self._live_view._active_brain.id)
            self._stack.setCurrentIndex(SESSION_HISTORY)

    def _show_wizard(self, template_key: str):
        self._wizard_view.load_template(template_key)
        self._stack.setCurrentIndex(WIZARD)

    def _show_brain_edit(self, brain_id: str):
        self._brain_edit_view.load_brain(brain_id)
        self._stack.setCurrentIndex(BRAIN_EDIT)

    def _show_new_brain(self):
        self._brain_edit_view.load_new()
        self._stack.setCurrentIndex(BRAIN_EDIT)

    def _on_api_key_submitted(self, key: str):
        self._stack.setCurrentIndex(PICKER)

    def _on_brain_created(self, brain_id: str):
        self._finish_onboarding(brain_id)

    def _on_brain_saved(self, brain_id: str):
        settings = UserSettingsRepository(self._app.db).get()
        if not settings.onboarding_complete:
            self._finish_onboarding(brain_id)
        else:
            self._live_view.refresh_brains()
            self._live_view.set_active_brain(brain_id)
            self._stack.setCurrentIndex(LIVE)

    def _finish_onboarding(self, brain_id: str):
        settings_repo = UserSettingsRepository(self._app.db)
        settings = settings_repo.get()
        settings.onboarding_complete = True
        settings_repo.update(settings)

        self._live_view.refresh_brains()
        self._live_view.set_active_brain(brain_id)
        self._stack.setCurrentIndex(LIVE)

    def _on_brain_deleted(self):
        brains = self._app.brain_repo.get_all()
        if brains:
            self._live_view.refresh_brains()
            self._stack.setCurrentIndex(LIVE)
        else:
            self._stack.setCurrentIndex(PICKER)

    def _return_to_live(self):
        self._live_view.refresh_brains()
        self._stack.setCurrentIndex(LIVE)

    def start_recording(self):
        self._live_view._start_recording()

    def stop_recording(self):
        self._live_view._stop_recording()

    def set_detached(self, detached: bool):
        self._live_view.set_detached(detached)
