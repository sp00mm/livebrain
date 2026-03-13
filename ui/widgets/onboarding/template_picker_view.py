from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Qt, Signal

import qtawesome as qta

from ui.styles import BASE_STYLE, ACCENT, TEXT_SECONDARY, BG_CARD, BG_CARD_HOVER, TEXT_PRIMARY, BORDER_COLOR
from templates import TEMPLATES


class TemplateCard(QFrame):
    clicked = Signal(str)

    def __init__(self, key, name, description, parent=None):
        super().__init__(parent)
        self._key = key
        self.setObjectName('templateCard')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(90)
        self.setStyleSheet(f'''
            QFrame#templateCard {{
                background-color: {BG_CARD};
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 16px;
            }}
            QFrame#templateCard:hover {{
                background-color: {BG_CARD_HOVER};
                border: 1px solid {BORDER_COLOR};
            }}
        ''')

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        name_label = QLabel(name)
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        name_label.setStyleSheet(f'font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY}; border: none;')
        layout.addWidget(name_label)

        desc_label = QLabel(description)
        desc_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        desc_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px; border: none;')
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        layout.addStretch()

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

        back_row = QHBoxLayout()
        self._back_btn = QPushButton()
        self._back_btn.setObjectName('iconBtn')
        self._back_btn.setIcon(qta.icon('mdi.arrow-left', color='#888888'))
        self._back_btn.setFixedSize(24, 24)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self.navigate_back.emit)
        self._back_btn.setVisible(False)
        back_row.addWidget(self._back_btn)
        back_row.addStretch()
        layout.addLayout(back_row)

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

    def set_show_back(self, show: bool):
        self._back_btn.setVisible(show)
