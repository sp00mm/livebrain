from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt

from ui.styles import (
    BG_CARD, TEXT_SECONDARY, TEXT_DIM,
    FEED_DIVIDER, FEED_QUESTION_BG, FEED_ANSWER_ACTIVE,
    FEED_ANSWER_FADED, FEED_STATUS_COLOR
)


class TranscriptDividerItem(QFrame):
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        line = QLabel(f'--- {text} ---' if text else '---')
        line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        line.setStyleSheet(f'color: {FEED_DIVIDER}; font-size: 11px;')
        layout.addWidget(line)

        self._detail = QLabel('')
        self._detail.setWordWrap(True)
        self._detail.setVisible(False)
        self._detail.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px; padding: 4px 8px;')
        layout.addWidget(self._detail)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expanded = False

    def set_detail(self, text: str):
        self._detail.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._detail.text():
            self._expanded = not self._expanded
            self._detail.setVisible(self._expanded)
        super().mousePressEvent(event)


class QuestionItem(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f'''
            color: {TEXT_SECONDARY};
            font-size: 12px;
            font-weight: 500;
        ''')
        layout.addWidget(label)

        self.setStyleSheet(f'''
            QFrame {{
                background-color: {FEED_QUESTION_BG};
                border-radius: 6px;
            }}
        ''')


class AnswerItem(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        self._label = QLabel('')
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._label.setStyleSheet(f'color: {FEED_ANSWER_ACTIVE}; font-size: 13px;')
        layout.addWidget(self._label)

        self._text = ''

    def append_delta(self, delta: str):
        self._text += delta
        self._label.setText(self._text)

    def set_complete(self):
        self._label.setStyleSheet(f'color: {FEED_ANSWER_FADED}; font-size: 13px;')

    def set_text(self, text: str):
        self._text = text
        self._label.setText(text)

    def get_text(self) -> str:
        return self._text


class StatusItem(QLabel):
    def __init__(self, text: str = '', parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f'color: {FEED_STATUS_COLOR}; font-size: 11px; font-style: italic; padding: 2px 10px;')


class ChatFeedWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_scrolled_up = False
        self._answer_items: dict[str, AnswerItem] = {}
        self._status_items: dict[str, StatusItem] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._layout.addStretch()

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

        vbar = self._scroll.verticalScrollBar()
        vbar.rangeChanged.connect(self._on_range_changed)
        vbar.valueChanged.connect(self._on_scroll)

    def add_transcript_divider(self, text: str = '', detail: str = '') -> TranscriptDividerItem:
        item = TranscriptDividerItem(text)
        if detail:
            item.set_detail(detail)
        self._insert_item(item)
        return item

    def add_question(self, text: str) -> QuestionItem:
        item = QuestionItem(text)
        self._insert_item(item)
        return item

    def add_answer(self, thread_id: str) -> AnswerItem:
        item = AnswerItem()
        self._answer_items[thread_id] = item
        self._insert_item(item)
        return item

    def append_answer_delta(self, thread_id: str, delta: str):
        if thread_id in self._answer_items:
            self._answer_items[thread_id].append_delta(delta)
            self._auto_scroll()

    def set_answer_complete(self, thread_id: str):
        if thread_id in self._answer_items:
            self._answer_items[thread_id].set_complete()

    def update_status(self, thread_id: str, text: str):
        if thread_id in self._status_items:
            self._status_items[thread_id].setText(text)
        else:
            item = StatusItem(text)
            self._status_items[thread_id] = item
            self._insert_item(item)

    def remove_status(self, thread_id: str):
        if thread_id in self._status_items:
            item = self._status_items.pop(thread_id)
            item.setVisible(False)
            item.deleteLater()

    def clear_feed(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._answer_items.clear()
        self._status_items.clear()

    def load_from_items(self, items):
        self.clear_feed()
        for item in items:
            if item.item_type.value == 'transcript':
                self.add_transcript_divider(item.content)
            elif item.item_type.value == 'question':
                self.add_question(item.content)
            elif item.item_type.value == 'answer':
                answer = self.add_answer(item.thread_id or item.id)
                answer.set_text(item.content)
                answer.set_complete()

    def _insert_item(self, widget: QWidget):
        self._layout.insertWidget(self._layout.count() - 1, widget)
        self._auto_scroll()

    def _auto_scroll(self):
        if not self._user_scrolled_up:
            vbar = self._scroll.verticalScrollBar()
            vbar.setValue(vbar.maximum())

    def _on_range_changed(self, min_val, max_val):
        if not self._user_scrolled_up:
            self._scroll.verticalScrollBar().setValue(max_val)

    def _on_scroll(self, value):
        vbar = self._scroll.verticalScrollBar()
        self._user_scrolled_up = value < vbar.maximum() - 20
