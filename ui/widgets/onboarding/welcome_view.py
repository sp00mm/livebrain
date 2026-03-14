from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

from ui.styles import BASE_STYLE, ACCENT, TEXT_SECONDARY, FONT_FAMILY


class WelcomeView(QWidget):
    next_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(BASE_STYLE)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        brain_icon = QLabel()
        brain_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brain_icon.setPixmap(qta.icon('mdi.brain', color=ACCENT).pixmap(48, 48))
        layout.addWidget(brain_icon)

        title = QLabel('Livebrain')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'font-size: 32px; font-weight: 700; font-family: {FONT_FAMILY};')
        layout.addWidget(title)

        tagline = QLabel('Real-time AI for your meetings')
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 15px;')
        layout.addWidget(tagline)

        layout.addSpacing(24)

        btn = QPushButton('Get Started')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedWidth(200)
        btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {ACCENT};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 15px;
                font-weight: 600;
            }}
        ''')
        btn.clicked.connect(self.next_clicked)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
