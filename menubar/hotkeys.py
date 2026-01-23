from typing import Callable, Optional
from pynput import keyboard


class GlobalHotkeyManager:
    def __init__(self, on_toggle_recording: Callable):
        self._on_toggle_recording = on_toggle_recording
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def start(self):
        self._listener = keyboard.GlobalHotKeys({
            '<cmd>+<shift>+l': self._handle_toggle
        })
        self._listener.start()

    def stop(self):
        self._listener.stop()
        self._listener = None

    def _handle_toggle(self):
        self._on_toggle_recording()
