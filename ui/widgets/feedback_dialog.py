from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox
)
from PySide6.QtCore import Qt

from ui.styles import (
    STYLE_SHEET, BG_SECONDARY, TEXT_PRIMARY, TEXT_SECONDARY,
    BG_CARD, BG_CARD_HOVER, ACCENT
)


class FeedbackDialog(QDialog):
    def __init__(self, show_remember: bool = False, parent=None):
        super().__init__(parent)
        self.rating = None
        self.remember = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(STYLE_SHEET)
        self.setFixedWidth(300)
        self._build_ui(show_remember)

    def _build_ui(self, show_remember: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QLabel()
        card.setStyleSheet(f'''
            background-color: {BG_SECONDARY};
            border-radius: 12px;
            border: 1px solid #3a3a3a;
        ''')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 16)
        card_layout.setSpacing(16)

        title = QLabel('How was this session?')
        title.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 15px; font-weight: 600;')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        btn_row.addStretch()

        self._up_btn = QPushButton('\U0001f44d')
        self._down_btn = QPushButton('\U0001f44e')
        for btn in (self._up_btn, self._down_btn):
            btn.setFixedSize(56, 56)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f'''
                QPushButton {{
                    background-color: {BG_CARD};
                    border: 1px solid #3a3a3a;
                    border-radius: 28px;
                    font-size: 24px;
                }}
                QPushButton:hover {{
                    background-color: {BG_CARD_HOVER};
                }}
            ''')

        self._up_btn.clicked.connect(lambda: self._submit(1))
        self._down_btn.clicked.connect(lambda: self._submit(-1))

        btn_row.addWidget(self._up_btn)
        btn_row.addWidget(self._down_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        desc = QLabel(
            'Help improve LiveBrain \u2014 if you rate this session, '
            'anonymized data may be shared to help make the product better.'
        )
        desc.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(desc)

        if show_remember:
            self._remember_check = QCheckBox('Remember my choice')
            self._remember_check.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
            card_layout.addWidget(self._remember_check, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            self._remember_check = None

        no_thanks = QPushButton('No thanks')
        no_thanks.setCursor(Qt.CursorShape.PointingHandCursor)
        no_thanks.setStyleSheet(f'''
            QPushButton {{
                background: transparent;
                border: none;
                color: {TEXT_SECONDARY};
                font-size: 12px;
                text-decoration: underline;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
            }}
        ''')
        no_thanks.clicked.connect(self._dismiss)
        card_layout.addWidget(no_thanks, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(card)

    def _submit(self, value: int):
        self.rating = value
        self.remember = self._remember_check.isChecked() if self._remember_check else False
        self.accept()

    def _dismiss(self):
        self.rating = None
        self.remember = self._remember_check.isChecked() if self._remember_check else False
        self.reject()
