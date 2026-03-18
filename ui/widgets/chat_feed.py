import re
import subprocess

import qtawesome as qta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QApplication, QTextBrowser,
    QPushButton, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QUrl, Signal, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QDesktopServices

from models import FeedItemType
from ui.styles import (
    BG_CARD, BG_SECONDARY, BG_BUTTON, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
    FEED_QUESTION_BG, FEED_ANSWER_ACTIVE,
    FEED_ANSWER_FADED, FEED_STATUS_COLOR, FONT_FAMILY, LINK_COLOR,
    TRANSCRIPT_YOU_COLOR, TRANSCRIPT_OTHER_COLOR,
    ROLE_QUESTION_COLOR, ROLE_ANSWER_COLOR, ROLE_TOOL_COLOR, QUERY_GROUP_BORDER
)
from ui.markdown_renderer import render_markdown


class TranscriptItem(QFrame):
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(1)

        lines = text.strip().split('\n')
        for line in lines:
            if not line.strip():
                continue
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 0, 0, 0)

            is_user = line.startswith('You:')
            color = TRANSCRIPT_YOU_COLOR if is_user else TRANSCRIPT_OTHER_COLOR

            dot = QLabel('\u2022')
            dot.setFixedWidth(10)
            dot.setStyleSheet(f'color: {color}; font-size: 14px;')
            dot.setAlignment(Qt.AlignmentFlag.AlignTop)
            row.addWidget(dot)

            speaker = 'You' if is_user else 'Other'
            content = line.split(':', 1)[1].strip() if ':' in line else line

            text_label = QLabel(f'<b>{speaker}</b>  {content}')
            text_label.setWordWrap(True)
            text_label.setStyleSheet(f'color: {color}; font-size: 11px;')
            row.addWidget(text_label, 1)

            layout.addLayout(row)


TranscriptDividerItem = TranscriptItem


class QuestionItem(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(6)

        dot = QLabel('\u2022')
        dot.setFixedWidth(10)
        dot.setStyleSheet(f'color: {ROLE_QUESTION_COLOR}; font-size: 14px;')
        dot.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(dot)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 500;')
        row.addWidget(label, 1)

        self.setStyleSheet(f'QFrame {{ background-color: {FEED_QUESTION_BG}; border-radius: 6px; }}')


class AnswerItem(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._dot = QLabel('\u2022')
        self._dot.setFixedWidth(10)
        self._dot.setStyleSheet(f'color: {ROLE_ANSWER_COLOR}; font-size: 14px;')
        self._dot.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(self._dot)

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
        row.addWidget(self._browser, 1)

        self._text = ''
        self._faded = False
        self._file_refs = []
        self._pending_delta = ''

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(50)
        self._render_timer.timeout.connect(self._flush_delta)

    def append_delta(self, delta: str):
        self._pending_delta += delta
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _flush_delta(self):
        if self._pending_delta:
            self._text += self._pending_delta
            self._pending_delta = ''
            html = render_markdown(self._text)
            self._browser.setHtml(self._wrap_html(html))
            self._adjust_height()

    def set_complete(self, file_refs=None):
        if self._pending_delta:
            self._text += self._pending_delta
            self._pending_delta = ''
        self._render_timer.stop()
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
code {{ background: {BG_SECONDARY}; padding: 1px 4px; border-radius: 3px; font-size: 11px; }}
pre {{ background: {BG_SECONDARY}; padding: 8px; border-radius: 6px; }}
pre code {{ background: none; padding: 0; }}
a {{ color: {LINK_COLOR}; }}
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

        header = QHBoxLayout()
        header.setSpacing(6)

        dot = QLabel('\u2022')
        dot.setFixedWidth(10)
        dot.setStyleSheet(f'color: {ROLE_TOOL_COLOR}; font-size: 14px;')
        dot.setAlignment(Qt.AlignmentFlag.AlignTop)
        header.addWidget(dot)

        summary = QLabel(detail.summary)
        summary.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 13px;')
        summary.setWordWrap(True)
        header.addWidget(summary, 1)

        layout.addLayout(header)

        self._detail_widget = QWidget()
        self._detail_widget.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(16, 4, 0, 0)
        detail_layout.setSpacing(2)

        for key, value in detail.details:
            text = f'{key}: {value}' if value else key
            label = QLabel(text)
            label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')
            label.setWordWrap(True)
            detail_layout.addWidget(label)

        layout.addWidget(self._detail_widget)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expanded = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._expanded = not self._expanded
            self._detail_widget.setVisible(self._expanded)
        super().mousePressEvent(event)


class StatusItem(QFrame):
    def __init__(self, text: str = '', parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(6)

        dot = QLabel('\u2022')
        dot.setFixedWidth(10)
        dot.setStyleSheet(f'color: {FEED_STATUS_COLOR}; font-size: 14px;')
        dot.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(dot)

        self._text_label = QLabel(text)
        self._text_label.setStyleSheet(f'color: {FEED_STATUS_COLOR}; font-size: 11px; font-style: italic;')
        row.addWidget(self._text_label, 1)

    def setText(self, text: str):
        self._text_label.setText(text)


class QueryGroup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('queryGroup')
        self.setStyleSheet(f'QFrame#queryGroup {{ border-left: 2px solid {QUERY_GROUP_BORDER}; margin-left: 4px; padding-left: 4px; }}')
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 0, 4)
        self._layout.setSpacing(4)
        self._status_item = None
        self._answer_item = None

    def add_question(self, text: str) -> QuestionItem:
        item = QuestionItem(text)
        self._layout.addWidget(item)
        return item

    def add_answer(self) -> AnswerItem:
        self._answer_item = AnswerItem()
        self._layout.addWidget(self._answer_item)
        return self._answer_item

    def update_status(self, text: str):
        if self._status_item:
            self._status_item.setText(text)
        else:
            self._status_item = StatusItem(text)
            idx = self._layout.count()
            if self._answer_item:
                idx = self._layout.indexOf(self._answer_item)
            self._layout.insertWidget(idx, self._status_item)

    def remove_status(self):
        if self._status_item:
            self._status_item.deleteLater()
            self._status_item = None

    def add_tool_call(self, detail) -> ToolCallItem:
        item = ToolCallItem(detail)
        idx = self._layout.count()
        if self._answer_item:
            idx = self._layout.indexOf(self._answer_item)
        self._layout.insertWidget(idx, item)
        return item


class FeedbackItem(QFrame):
    rated = Signal(int)
    dismissed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        prompt = QLabel('Help us improve \u00b7 rating may share anonymized data')
        prompt.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')
        row.addWidget(prompt)

        row.addStretch()

        for icon_name, rating in [('fa5s.thumbs-up', 1), ('fa5s.thumbs-down', -1)]:
            btn = QPushButton()
            btn.setIcon(qta.icon(icon_name, color=TEXT_DIM))
            btn.setFixedSize(22, 22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f'QPushButton {{ background: transparent; border: none; }} QPushButton:hover {{ background-color: {BG_BUTTON}; border-radius: 4px; }}')
            btn.clicked.connect(lambda _, r=rating: self._on_rated(r))
            row.addWidget(btn)

        dismiss_btn = QPushButton()
        dismiss_btn.setIcon(qta.icon('fa5s.times', color=TEXT_DIM))
        dismiss_btn.setFixedSize(22, 22)
        dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_btn.setStyleSheet(f'QPushButton {{ background: transparent; border: none; }} QPushButton:hover {{ background-color: {BG_BUTTON}; border-radius: 4px; }}')
        dismiss_btn.clicked.connect(self._on_dismissed)
        row.addWidget(dismiss_btn)

    def _on_rated(self, rating: int):
        self.rated.emit(rating)
        self._fade_out()

    def _on_dismissed(self):
        self.dismissed.emit()
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


class ExportItem(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        btn = QPushButton()
        btn.setIcon(qta.icon('mdi.file-export', color=TEXT_DIM))
        btn.setFixedSize(22, 22)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f'QPushButton {{ background: transparent; border: none; }} QPushButton:hover {{ background-color: {BG_BUTTON}; border-radius: 4px; }}')
        btn.clicked.connect(self.clicked.emit)
        row.addWidget(btn)

        label = QLabel('Save transcript')
        label.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')
        row.addWidget(label)

        row.addStretch()


class ChatFeedWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_scrolled_up = False
        self._query_groups: dict[str, QueryGroup] = {}

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

    def add_transcript(self, text: str = '') -> TranscriptItem:
        item = TranscriptItem(text)
        self._insert_item(item)
        return item

    def add_transcript_divider(self, text: str = '') -> TranscriptItem:
        return self.add_transcript(text)

    def add_question(self, text: str) -> QuestionItem:
        item = QuestionItem(text)
        self._insert_item(item)
        return item

    def add_answer(self, thread_id: str) -> AnswerItem:
        group = self.add_query_group(thread_id, '')
        return group._answer_item

    def add_query_group(self, thread_id: str, question_text: str) -> QueryGroup:
        group = QueryGroup()
        if question_text:
            group.add_question(question_text)
        group.add_answer()
        self._query_groups[thread_id] = group
        self._insert_item(group)
        return group

    def append_answer_delta(self, thread_id: str, delta: str):
        self._query_groups[thread_id]._answer_item.append_delta(delta)
        self._auto_scroll()

    def set_answer_complete(self, thread_id: str, file_refs=None):
        self._query_groups[thread_id]._answer_item.set_complete(file_refs)

    def update_status(self, thread_id: str, text: str):
        self._query_groups[thread_id].update_status(text)

    def remove_status(self, thread_id: str):
        self._query_groups[thread_id].remove_status()

    def add_tool_call(self, thread_id: str, detail) -> ToolCallItem:
        return self._query_groups[thread_id].add_tool_call(detail)

    def add_feedback_item(self) -> FeedbackItem:
        item = FeedbackItem()
        self._insert_item(item)
        return item

    def add_export_item(self) -> ExportItem:
        item = ExportItem()
        self._insert_item(item)
        return item

    def clear_feed(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._query_groups.clear()

    def load_from_items(self, items):
        self.clear_feed()
        i = 0
        while i < len(items):
            item = items[i]
            if item.item_type == FeedItemType.TRANSCRIPT:
                self.add_transcript(item.content)
                i += 1
            elif item.item_type == FeedItemType.QUESTION:
                q_text = item.content
                i += 1
                if i < len(items) and items[i].item_type == FeedItemType.ANSWER:
                    answer_item = items[i]
                    tid = answer_item.thread_id or answer_item.id
                    group = self.add_query_group(tid, q_text)
                    group._answer_item.set_text(answer_item.content)
                    group._answer_item.set_complete()
                    i += 1
                else:
                    self.add_question(q_text)
            elif item.item_type == FeedItemType.ANSWER:
                tid = item.thread_id or item.id
                group = self.add_query_group(tid, '')
                group._answer_item.set_text(item.content)
                group._answer_item.set_complete()
                i += 1
            else:
                i += 1

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
