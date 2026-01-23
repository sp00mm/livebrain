from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QPainter, QPainterPath, QBrush

from AppKit import NSScreen


class PopoverWindow(QWidget):
    def __init__(self, content_widget: QWidget):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(content_widget)

        self.setFixedSize(400, 520)

        QApplication.instance().installEventFilter(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 10, 10)

        painter.fillPath(path, QBrush(QColor(30, 30, 30, 245)))
        painter.setPen(QColor(60, 60, 60))
        painter.drawPath(path)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            if self.isVisible():
                global_pos = event.globalPosition().toPoint()
                if not self.geometry().contains(global_pos):
                    self.hide()
                    return True
        return False

    def position_below_status_item(self, button_frame):
        screen_height = NSScreen.mainScreen().frame().size.height
        button_x = button_frame.origin.x
        button_width = button_frame.size.width

        x = int(button_x + button_width / 2 - self.width() / 2)
        y = int(screen_height - button_frame.origin.y + 4)

        screen = QApplication.primaryScreen().geometry()
        if x + self.width() > screen.width():
            x = screen.width() - self.width() - 10
        if x < 10:
            x = 10

        self.move(x, y)

    def toggle(self, button_frame=None):
        if self.isVisible():
            self.hide()
        else:
            self.position_below_status_item(button_frame)
            self.show()
            self.raise_()
            self.activateWindow()

    def hideEvent(self, event):
        super().hideEvent(event)
