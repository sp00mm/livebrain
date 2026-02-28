from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QFrame, QFileDialog
)
from PySide6.QtCore import Qt, Signal

import qtawesome as qta

from models import Session, FeedItemType
from services.database import Database, SessionRepository, ChatFeedItemRepository
from ui.styles import (
    STYLE_SHEET, BG_CARD, BG_CARD_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY
)
from ui.widgets.chat_feed import ChatFeedWidget


class SessionCard(QFrame):
    clicked = Signal(object)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f'''
            QFrame {{
                background-color: {BG_CARD};
                border-radius: 6px;
            }}
            QFrame:hover {{
                background-color: {BG_CARD_HOVER};
            }}
        ''')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        name = QLabel(session.name or 'Untitled Session')
        name.setStyleSheet(f'color: {TEXT_PRIMARY}; font-weight: 500;')
        layout.addWidget(name)

        date_str = session.created_at.strftime('%b %d, %Y  %I:%M %p') if session.created_at else ''
        date = QLabel(date_str)
        date.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
        layout.addWidget(date)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.session)
        super().mousePressEvent(event)


class SessionHistoryView(QWidget):
    navigate_back = Signal()

    def __init__(self, db: Database):
        super().__init__()
        self._db = db
        self._session_repo = SessionRepository(db)
        self._feed_repo = ChatFeedItemRepository(db)
        self._current_brain_id = None
        self._current_session_id = None

        self.setStyleSheet(STYLE_SHEET)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        header.setSpacing(8)

        back_btn = QPushButton()
        back_btn.setObjectName('iconBtn')
        back_btn.setIcon(qta.icon('mdi.arrow-left', color='#888888'))
        back_btn.setFixedSize(24, 24)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.navigate_back.emit)
        header.addWidget(back_btn)

        title = QLabel('Session History')
        title.setStyleSheet(f'color: {TEXT_PRIMARY}; font-weight: 600; font-size: 14px;')
        header.addWidget(title, 1)

        self._export_btn = QPushButton()
        self._export_btn.setObjectName('iconBtn')
        self._export_btn.setIcon(qta.icon('mdi.download', color='#888888'))
        self._export_btn.setFixedSize(24, 24)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setToolTip('Export as text')
        self._export_btn.setVisible(False)
        self._export_btn.clicked.connect(self._export_transcript)
        header.addWidget(self._export_btn)

        layout.addLayout(header)

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()
        self._list_scroll.setWidget(self._list_widget)
        layout.addWidget(self._list_scroll)

        self._feed = ChatFeedWidget()
        self._feed.setVisible(False)
        layout.addWidget(self._feed, 1)

    def load_brain(self, brain_id: str):
        self._current_brain_id = brain_id
        self._current_session_id = None
        self._feed.setVisible(False)
        self._list_scroll.setVisible(True)
        self._export_btn.setVisible(False)
        self._refresh_list()

    def _refresh_list(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sessions = self._session_repo.get_recent_for_brain(self._current_brain_id, limit=50)
        for session in sessions:
            card = SessionCard(session)
            card.clicked.connect(self._on_session_clicked)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _on_session_clicked(self, session: Session):
        self._current_session_id = session.id
        items = self._feed_repo.get_by_session(session.id)
        self._list_scroll.setVisible(False)
        self._feed.setVisible(True)
        self._export_btn.setVisible(True)
        self._feed.load_from_items(items)

    def _export_transcript(self):
        items = self._feed_repo.get_by_session(self._current_session_id)
        lines = []
        for item in items:
            if item.item_type == FeedItemType.TRANSCRIPT:
                lines.append(f'[Transcript]\n{item.content}\n')
            elif item.item_type == FeedItemType.QUESTION:
                lines.append(f'Q: {item.content}\n')
            elif item.item_type == FeedItemType.ANSWER:
                lines.append(f'A: {item.content}\n')
        text = '\n'.join(lines)

        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Session', 'session_transcript.txt', 'Text Files (*.txt)'
        )
        if path:
            with open(path, 'w') as f:
                f.write(text)
