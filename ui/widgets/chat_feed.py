import re
import subprocess

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QTextBrowser, QApplication,
    QPushButton, QCheckBox, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QUrl, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QDesktopServices

from models import FeedItemType
from ui.styles import (
    BG_CARD, TEXT_SECONDARY, TEXT_DIM,
    FEED_QUESTION_BG, FEED_ANSWER_ACTIVE,
    FEED_ANSWER_FADED, FEED_STATUS_COLOR, FONT_FAMILY,
    TRANSCRIPT_YOU_COLOR, TRANSCRIPT_OTHER_COLOR
)
from ui.markdown_renderer import render_markdown


class TranscriptDividerItem(QFrame):
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)
        self._layout.setSpacing(2)
        self._build_lines(text)

    def _build_lines(self, text: str):
        if not text:
            return
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('You: '):
                color = TRANSCRIPT_YOU_COLOR
            elif line.startswith('Other: '):
                color = TRANSCRIPT_OTHER_COLOR
            else:
                color = TEXT_DIM
            label = QLabel(line)
            label.setWordWrap(True)
            label.setStyleSheet(f'color: {color}; font-size: 11px;')
            self._layout.addWidget(label)



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
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 8)

        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        self._browser.setOpenExternalLinks(False)
        self._browser.anchorClicked.connect(self._on_link_clicked)
        self._browser.setFrameShape(QFrame.Shape.NoFrame)
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._browser.document().setDocumentMargin(0)
        self._browser.setStyleSheet('QTextBrowser { background: transparent; border: none; }')
        self._layout.addWidget(self._browser)

        self._text = ''
        self._faded = False
        self._file_refs = []

    def append_delta(self, delta: str):
        self._text += delta
        html = render_markdown(self._text)
        self._browser.setHtml(self._wrap_html(html))
        self._adjust_height()

    def set_complete(self, file_refs=None):
        self._faded = True
        self._file_refs = file_refs or []
        html = render_markdown(self._text)
        html = self._linkify_sources(html)
        self._browser.setHtml(self._wrap_html(html))
        self._adjust_height()

    def _linkify_sources(self, html: str) -> str:
        if not self._file_refs:
            return html
        ref_map = {ref.display_name: ref for ref in self._file_refs}

        def replace_href(match):
            href = match.group(1)
            if href not in ref_map:
                return match.group(0)
            ref = ref_map[href]
            fragment = f'#page={ref.source_meta["page"]}' if ref.source_meta and ref.source_meta.get('page') else ''
            return f'<a href="file://{ref.filepath}{fragment}">{match.group(2)}</a>'

        return re.sub(r'<a href="([^"]+)">(.+?)</a>', replace_href, html)

    def _on_link_clicked(self, url: QUrl):
        path = url.toLocalFile()
        if not path:
            QDesktopServices.openUrl(url)
            return
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            subprocess.Popen(['open', '-R', path])
        else:
            subprocess.Popen(['open', path])

    def set_text(self, text: str):
        self._text = text
        html = render_markdown(text)
        self._browser.setHtml(self._wrap_html(html))
        self._adjust_height()

    def get_text(self) -> str:
        return self._text

    def _wrap_html(self, body: str) -> str:
        color = FEED_ANSWER_FADED if self._faded else FEED_ANSWER_ACTIVE
        return f'''<style>
body {{ color: {color}; font-size: 13px; font-family: {FONT_FAMILY}; margin: 0; padding: 0; }}
code {{ background: #2a2a2a; padding: 1px 4px; border-radius: 3px; font-size: 12px; }}
pre {{ background: #2a2a2a; padding: 8px; border-radius: 6px; }}
pre code {{ background: none; padding: 0; }}
a {{ color: #6eb5ff; }}
h1, h2, h3 {{ margin: 8px 0 4px 0; }}
p {{ margin: 4px 0; }}
ul, ol {{ margin: 4px 0; padding-left: 20px; }}
</style>{body}'''

    def _adjust_height(self):
        doc = self._browser.document()
        doc.setTextWidth(self._browser.viewport().width())
        height = int(doc.size().height()) + 4
        self._browser.setMinimumHeight(height)
        self._browser.setMaximumHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._text:
            self._adjust_height()


class ToolCallItem(QFrame):
    def __init__(self, detail, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'QFrame {{ background-color: {BG_CARD}; border-radius: 6px; }}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        summary = QLabel(f'Searched: "{detail.query}"')
        summary.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self._detail_widget = QWidget()
        self._detail_widget.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(0, 4, 0, 0)
        detail_layout.setSpacing(2)

        if detail.matched_files:
            files_text = ', '.join(detail.matched_files)
            files_label = QLabel(f'Found in: {files_text}')
            files_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')
            files_label.setWordWrap(True)
            detail_layout.addWidget(files_label)

        meta_label = QLabel(f'{detail.results_count} results \u00b7 {detail.duration_ms}ms')
        meta_label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')
        detail_layout.addWidget(meta_label)

        layout.addWidget(self._detail_widget)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expanded = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._expanded = not self._expanded
            self._detail_widget.setVisible(self._expanded)
        super().mousePressEvent(event)


class StatusItem(QLabel):
    def __init__(self, text: str = '', parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(f'color: {FEED_STATUS_COLOR}; font-size: 11px; font-style: italic; padding: 2px 10px;')


class FeedbackItem(QFrame):
    rated = Signal(int, bool)
    dismissed = Signal(bool)

    def __init__(self, show_remember=False, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'QFrame {{ background-color: {BG_CARD}; border-radius: 6px; }}')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(6)

        prompt = QLabel('How was this session?')
        prompt.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        row.addWidget(prompt)

        row.addStretch()

        for emoji, rating in [('\U0001f44d', 1), ('\U0001f44e', -1)]:
            btn = QPushButton(emoji)
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet('QPushButton { background: transparent; border: none; font-size: 16px; } QPushButton:hover { background-color: #3a3a3a; border-radius: 4px; }')
            btn.clicked.connect(lambda _, r=rating: self._on_rated(r))
            row.addWidget(btn)

        dismiss_btn = QPushButton('\u2715')
        dismiss_btn.setFixedSize(28, 28)
        dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_btn.setStyleSheet(f'QPushButton {{ background: transparent; border: none; color: {TEXT_DIM}; font-size: 14px; }} QPushButton:hover {{ color: {TEXT_SECONDARY}; }}')
        dismiss_btn.clicked.connect(self._on_dismissed)
        row.addWidget(dismiss_btn)

        layout.addLayout(row)

        desc = QLabel('Your rating may send anonymized session data to help improve LiveBrain.')
        desc.setStyleSheet(f'color: {TEXT_DIM}; font-size: 10px;')
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._remember_check = None
        if show_remember:
            self._remember_check = QCheckBox('Remember my choice')
            self._remember_check.setStyleSheet(f'QCheckBox {{ color: {TEXT_DIM}; font-size: 10px; }}')
            layout.addWidget(self._remember_check)

    def _remember(self) -> bool:
        return self._remember_check.isChecked() if self._remember_check else False

    def _on_rated(self, rating: int):
        self.rated.emit(rating, self._remember())
        self._fade_out()

    def _on_dismissed(self):
        self.dismissed.emit(self._remember())
        self._fade_out()

    def _fade_out(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b'opacity', self)
        anim.setDuration(300)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(self.deleteLater)
        anim.start()


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

    def add_transcript_divider(self, text: str = '') -> TranscriptDividerItem:
        item = TranscriptDividerItem(text)
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

    def set_answer_complete(self, thread_id: str, file_refs=None):
        if thread_id in self._answer_items:
            self._answer_items[thread_id].set_complete(file_refs)

    def update_status(self, thread_id: str, text: str):
        if thread_id in self._status_items:
            self._status_items[thread_id].setText(text)
        else:
            item = StatusItem(text)
            self._status_items[thread_id] = item
            self._insert_item(item)

    def add_tool_call(self, thread_id: str, detail) -> ToolCallItem:
        item = ToolCallItem(detail)
        self._insert_item(item)
        return item

    def remove_status(self, thread_id: str):
        if thread_id in self._status_items:
            item = self._status_items.pop(thread_id)
            item.setVisible(False)
            item.deleteLater()

    def add_feedback_item(self, show_remember=False) -> FeedbackItem:
        item = FeedbackItem(show_remember=show_remember)
        self._insert_item(item)
        return item

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
            if item.item_type == FeedItemType.TRANSCRIPT:
                self.add_transcript_divider(item.content)
            elif item.item_type == FeedItemType.QUESTION:
                self.add_question(item.content)
            elif item.item_type == FeedItemType.ANSWER:
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
