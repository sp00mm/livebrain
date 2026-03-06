from collections import deque

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor

from ui.styles import USER_COLOR, TEXT_SECONDARY


class WaveformWidget(QWidget):
    BAR_COUNT = 40
    BAR_GAP = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mic_levels = deque(maxlen=self.BAR_COUNT)
        self._system_levels = deque(maxlen=self.BAR_COUNT)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def push_levels(self, mic_rms: float, system_rms: float):
        self._mic_levels.append(mic_rms)
        self._system_levels.append(system_rms)
        self.update()

    def clear(self):
        self._mic_levels.clear()
        self._system_levels.clear()
        self.update()

    def paintEvent(self, event):
        if not self._mic_levels:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        count = len(self._mic_levels)
        bar_width = max(1, (w - (count - 1) * self.BAR_GAP) // count)

        x = w - bar_width
        for i in range(count - 1, -1, -1):
            mic = self._mic_levels[i]
            sys_level = self._system_levels[i]
            combined = mic + sys_level
            bar_height = min(h, max(2, int(combined * h * 5)))

            color = QColor(USER_COLOR) if mic >= sys_level else QColor(TEXT_SECONDARY)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)

            y = (h - bar_height) // 2
            painter.drawRoundedRect(x, y, bar_width, bar_height, 1, 1)

            x -= (bar_width + self.BAR_GAP)
            if x < 0:
                break

        painter.end()
