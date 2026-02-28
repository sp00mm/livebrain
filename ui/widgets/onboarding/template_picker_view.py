from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Qt, Signal

from ui.styles import BASE_STYLE, ACCENT, TEXT_SECONDARY, BG_CARD, BG_CARD_HOVER, TEXT_PRIMARY
from templates import TEMPLATES


class TemplateCard(QFrame):
    clicked = Signal(str)

    def __init__(self, key, name, description, parent=None):
        super().__init__(parent)
        self._key = key
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f'''
            QFrame {{
                background-color: {BG_CARD};
                border-radius: 8px;
                padding: 16px;
            }}
            QFrame:hover {{
                background-color: {BG_CARD_HOVER};
            }}
        ''')

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        name_label = QLabel(name)
        name_label.setStyleSheet(f'font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY};')
        layout.addWidget(name_label)

        desc_label = QLabel(description)
        desc_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px;')
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)


class TemplatePickerView(QWidget):
    template_selected = Signal(str)
    custom_selected = Signal()
    navigate_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(BASE_STYLE)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        header = QLabel('What kind of meeting?')
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet('font-size: 22px; font-weight: 700;')
        layout.addWidget(header)

        layout.addSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(12)

        templates = list(TEMPLATES.values())
        for i, t in enumerate(templates):
            card = TemplateCard(t.key, t.name, t.description)
            card.clicked.connect(self.template_selected)
            grid.addWidget(card, i // 2, i % 2)

        layout.addLayout(grid)

        layout.addSpacing(8)

        custom_btn = QPushButton('Build Your Own')
        custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        custom_btn.setFixedWidth(200)
        custom_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {ACCENT};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 15px;
                font-weight: 600;
            }}
        ''')
        custom_btn.clicked.connect(self.custom_selected)
        layout.addWidget(custom_btn, alignment=Qt.AlignmentFlag.AlignCenter)
