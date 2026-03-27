import sys
from typing import Callable, Optional
from pynput import keyboard

HOTKEY = '<cmd>+<shift>+l' if sys.platform == 'darwin' else '<ctrl>+<shift>+l'


class GlobalHotkeyManager:
    def __init__(self, on_toggle_recording: Callable):
        self._on_toggle_recording = on_toggle_recording
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def start(self):
        self._listener = keyboard.GlobalHotKeys({
            HOTKEY: self._handle_toggle
        })
        self._listener.start()

    def stop(self):
        self._listener.stop()
        self._listener = None

    def _handle_toggle(self):
        self._on_toggle_recording()
