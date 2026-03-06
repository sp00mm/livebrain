from collections import deque

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor

from ui.styles import USER_COLOR, TEXT_SECONDARY


class WaveformWidget(QWidget):
    BAR_COUNT = 40
    BAR_GAP = 2
    _COLOR_MIC = QColor(USER_COLOR)
    _COLOR_SYS = QColor(TEXT_SECONDARY)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._levels = deque(maxlen=self.BAR_COUNT)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def push_levels(self, mic_rms: float, system_rms: float):
        self._levels.append((mic_rms, system_rms))
        self.update()

    def clear(self):
        self._levels.clear()
        self.update()

    def paintEvent(self, event):
        if not self._levels:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        w = self.width()
        h = self.height()
        bar_width = max(1, (w - (self.BAR_COUNT - 1) * self.BAR_GAP) // self.BAR_COUNT)

        x = w - bar_width
        for i in range(len(self._levels) - 1, -1, -1):
            mic, sys_level = self._levels[i]
            combined = mic + sys_level
            bar_height = min(h, max(2, int(combined * h * 5)))

            painter.setBrush(self._COLOR_MIC if mic >= sys_level else self._COLOR_SYS)

            y = (h - bar_height) // 2
            painter.drawRoundedRect(x, y, bar_width, bar_height, 1, 1)

            x -= (bar_width + self.BAR_GAP)

        painter.end()
