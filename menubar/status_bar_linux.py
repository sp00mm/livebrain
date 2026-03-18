import os
import sys
from typing import Callable

from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QRect


class StatusBarController:
    def __init__(self, on_click: Callable, on_quit: Callable):
        self._on_click = on_click
        self._tray = QSystemTrayIcon()
        self._load_icons()
        self._tray.setIcon(self._icon_normal or QIcon())
        self._tray.activated.connect(self._on_activated)

        menu = QMenu()
        menu.addAction('Open Livebrain', on_click)
        menu.addSeparator()
        menu.addAction('Quit', on_quit)
        self._tray.setContextMenu(menu)
        self._tray.show()

    def _load_icons(self):
        resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'resources')
        if not os.path.exists(resources_dir):
            resources_dir = os.path.join(os.path.dirname(sys.executable), 'resources')

        self._icon_normal = QIcon(os.path.join(resources_dir, 'icon.png'))
        self._icon_recording = QIcon(os.path.join(resources_dir, 'icon_recording.png'))

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_click()

    def set_recording(self, recording: bool):
        self._tray.setIcon(self._icon_recording if recording else self._icon_normal)

    def get_button_frame(self):
        return self._tray.geometry()
