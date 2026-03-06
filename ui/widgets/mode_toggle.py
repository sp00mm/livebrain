from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, Signal

from ui.styles import ACCENT, BG_BUTTON, TEXT_SECONDARY


class ModeToggle(QWidget):
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = 'live_captions'

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._live_btn = QPushButton('Live Captions')
        self._full_btn = QPushButton('Full Transcription')

        for btn in (self._live_btn, self._full_btn):
            btn.setFixedHeight(22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            font = btn.font()
            font.setPixelSize(11)
            btn.setFont(font)

        self._live_btn.clicked.connect(lambda: self.set_mode('live_captions'))
        self._full_btn.clicked.connect(lambda: self.set_mode('full_transcription'))

        layout.addWidget(self._live_btn)
        layout.addWidget(self._full_btn)

        self._update_styles()

    def current_mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        if mode == self._mode:
            return
        self._mode = mode
        self._update_styles()
        self.mode_changed.emit(mode)

    def _update_styles(self):
        active = (
            f'background-color: {ACCENT}; color: white; '
            f'border: none; padding: 0 8px;'
        )
        inactive = (
            f'background-color: {BG_BUTTON}; color: {TEXT_SECONDARY}; '
            f'border: none; padding: 0 8px;'
        )

        left_radius = (
            'border-top-left-radius: 4px; border-bottom-left-radius: 4px; '
            'border-top-right-radius: 0; border-bottom-right-radius: 0;'
        )
        right_radius = (
            'border-top-left-radius: 0; border-bottom-left-radius: 0; '
            'border-top-right-radius: 4px; border-bottom-right-radius: 4px;'
        )

        is_live = self._mode == 'live_captions'
        self._live_btn.setStyleSheet(
            (active if is_live else inactive) + left_radius
        )
        self._full_btn.setStyleSheet(
            (inactive if is_live else active) + right_radius
        )
