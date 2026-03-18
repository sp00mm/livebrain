import sys

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QApplication, QPushButton, QLabel
from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QBrush


class DetachedWindow(QWidget):
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Livebrain')
        self.setMinimumSize(480, 580)
        self.setStyleSheet('background-color: #1e1e1e;')
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)

    def set_content(self, widget: QWidget):
        self._layout.addWidget(widget)

    def take_content(self) -> QWidget:
        return self._layout.takeAt(0).widget()

    def closeEvent(self, event):
        self.closed.emit()
        event.ignore()


class _TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self._window = parent
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)

        title = QLabel('Livebrain')
        title.setStyleSheet('color: #aaa; font-size: 12px; font-weight: bold; background: transparent;')
        layout.addWidget(title)
        layout.addStretch()

        close_btn = QPushButton('\u2715')
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            'QPushButton { color: #aaa; background: transparent; border: none; font-size: 14px; }'
            'QPushButton:hover { color: #fff; background: #444; border-radius: 12px; }'
        )
        close_btn.clicked.connect(self._window.hide)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle:
                handle.startSystemMove()


class PopoverWindow(QWidget):
    def __init__(self, content_widget: QWidget):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)

        if sys.platform != 'darwin':
            self._title_bar = _TitleBar(self)
            self._layout.addWidget(self._title_bar)

        self._layout.addWidget(content_widget)

        self.setFixedSize(480, 580)

        QApplication.instance().installEventFilter(self)

    def set_content(self, widget: QWidget):
        self._layout.addWidget(widget)

    def take_content(self) -> QWidget:
        idx = self._layout.count() - 1
        return self._layout.takeAt(idx).widget()

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
        if sys.platform == 'darwin':
            from AppKit import NSScreen
            screen_height = NSScreen.mainScreen().frame().size.height
            button_x = button_frame.origin.x
            button_width = button_frame.size.width
            x = int(button_x + button_width / 2 - self.width() / 2)
            y = int(screen_height - button_frame.origin.y + 4)
        else:
            x = button_frame.x() + button_frame.width() // 2 - self.width() // 2
            y = button_frame.y() + button_frame.height() + 4

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
