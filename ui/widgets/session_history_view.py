from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QFrame, QFileDialog
)
from PySide6.QtCore import Qt, Signal

import qtawesome as qta

from audio.storage import AudioStorage
from models import Session
from services.database import Database, SessionRepository, ChatFeedItemRepository, TranscriptEntryRepository
from services.export_service import build_export_markdown
from ui.styles import (
    STYLE_SHEET, BG_CARD, BG_CARD_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT
)
from ui.threads import WhisperTranscriptionThread
from ui.widgets.chat_feed import ChatFeedWidget


class SessionCard(QFrame):
    clicked = Signal(object)

    def __init__(self, session: Session, qa_count: int = 0, parent=None):
        super().__init__(parent)
        self.session = session
        self.setObjectName('sessionCard')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f'''
            QFrame#sessionCard {{
                background-color: {BG_CARD};
                border-radius: 6px;
            }}
            QFrame#sessionCard:hover {{
                background-color: {BG_CARD_HOVER};
            }}
        ''')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(2)

        date_str = session.created_at.strftime('%b %d, %Y  %I:%M %p') if session.created_at else ''
        date = QLabel(date_str)
        date.setStyleSheet(f'color: {TEXT_PRIMARY}; font-weight: 500; font-size: 12px;')
        left.addWidget(date)

        count_label = QLabel(f'{qa_count} question{"s" if qa_count != 1 else ""}')
        count_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
        left.addWidget(count_label)

        layout.addLayout(left, 1)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.session)
        super().mousePressEvent(event)


class SessionHistoryView(QWidget):
    navigate_back = Signal()

    def __init__(self, db: Database, whisper_service):
        super().__init__()
        self._db = db
        self._whisper_service = whisper_service
        self._session_repo = SessionRepository(db)
        self._feed_repo = ChatFeedItemRepository(db)
        self._transcript_repo = TranscriptEntryRepository(db)
        self._current_brain_id = None
        self._current_session_id = None
        self._exclude_session_id = None
        self._in_feed_view = False
        self._whisper_thread = None

        self.setStyleSheet(STYLE_SHEET)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        header.setSpacing(8)

        self._back_btn = QPushButton()
        self._back_btn.setObjectName('iconBtn')
        self._back_btn.setIcon(qta.icon('mdi.arrow-left', color='#888888'))
        self._back_btn.setFixedSize(24, 24)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.clicked.connect(self._handle_back)
        header.addWidget(self._back_btn)

        title = QLabel('Session History')
        title.setStyleSheet(f'color: {TEXT_PRIMARY}; font-weight: 600; font-size: 14px;')
        header.addWidget(title, 1)

        self._transcribe_btn = QPushButton('Transcribe')
        self._transcribe_btn.setFixedHeight(22)
        self._transcribe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._transcribe_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {ACCENT};
                border: none;
                border-radius: 4px;
                padding: 0 8px;
                color: white;
                font-size: 11px;
            }}
        ''')
        self._transcribe_btn.setVisible(False)
        self._transcribe_btn.clicked.connect(self._on_transcribe_clicked)
        header.addWidget(self._transcribe_btn)

        self._export_btn = QPushButton()
        self._export_btn.setObjectName('iconBtn')
        self._export_btn.setIcon(qta.icon('mdi.download', color='#888888'))
        self._export_btn.setFixedSize(24, 24)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setToolTip('Export session')
        self._export_btn.setVisible(False)
        self._export_btn.clicked.connect(self._export_transcript)
        header.addWidget(self._export_btn)

        self._delete_btn = QPushButton()
        self._delete_btn.setObjectName('iconBtn')
        self._delete_btn.setIcon(qta.icon('mdi.delete-outline', color='#888888'))
        self._delete_btn.setFixedSize(24, 24)
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.setToolTip('Delete session')
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(self._delete_session)
        header.addWidget(self._delete_btn)

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

    def load_brain(self, brain_id: str, exclude_session_id: str = None):
        self._current_brain_id = brain_id
        self._current_session_id = None
        self._exclude_session_id = exclude_session_id
        self._in_feed_view = False
        self._feed.setVisible(False)
        self._list_scroll.setVisible(True)
        self._transcribe_btn.setVisible(False)
        self._export_btn.setVisible(False)
        self._delete_btn.setVisible(False)
        self._refresh_list()

    def _handle_back(self):
        if self._in_feed_view:
            self._show_list()
        else:
            self.navigate_back.emit()

    def _show_list(self):
        self._in_feed_view = False
        self._feed.setVisible(False)
        self._list_scroll.setVisible(True)
        self._transcribe_btn.setVisible(False)
        self._export_btn.setVisible(False)
        self._delete_btn.setVisible(False)
        self._current_session_id = None

    def _refresh_list(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sessions = self._session_repo.get_recent_for_brain(self._current_brain_id, limit=50)
        session_ids = [s.id for s in sessions]
        ids_with_items = self._feed_repo.get_session_ids_with_items(session_ids)
        question_counts = self._feed_repo.get_question_counts(session_ids)

        shown = 0
        for session in sessions:
            if session.id == self._exclude_session_id:
                continue
            if session.id in ids_with_items:
                card = SessionCard(session, qa_count=question_counts.get(session.id, 0))
                card.clicked.connect(self._on_session_clicked)
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)
                shown += 1

        if shown == 0:
            empty = QLabel('No past sessions yet')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px; padding: 24px;')
            self._list_layout.insertWidget(0, empty)

    def _on_session_clicked(self, session: Session):
        self._current_session_id = session.id
        items = self._feed_repo.get_by_session(session.id)
        self._list_scroll.setVisible(False)
        self._feed.setVisible(True)
        self._transcribe_btn.setVisible(True)
        self._export_btn.setVisible(True)
        self._delete_btn.setVisible(True)
        self._feed.load_from_items(items)
        self._in_feed_view = True

    def _delete_session(self):
        self._session_repo.delete(self._current_session_id)
        self._show_list()
        self._refresh_list()

    def _export_transcript(self):
        text = build_export_markdown(self._current_session_id, self._db)
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Session', 'session-export.md', 'Markdown Files (*.md)'
        )
        if path:
            with open(path, 'w') as f:
                f.write(text)

    def _on_transcribe_clicked(self):
        session = self._session_repo.get(self._current_session_id)
        storage = AudioStorage(session.id)
        mic_path = storage.get_mic_path()
        system_path = storage.get_system_path()

        self._whisper_thread = WhisperTranscriptionThread(
            self._whisper_service,
            session.id,
            mic_path,
            system_path,
            session.created_at
        )
        self._transcribe_btn.setText('Transcribing...')
        self._transcribe_btn.setEnabled(False)
        self._whisper_thread.transcript_ready.connect(self._on_whisper_complete)
        self._whisper_thread.start()

    def _on_whisper_complete(self, entries: list):
        for entry in entries:
            self._transcript_repo.create(entry)
        self._whisper_thread = None
        self._transcribe_btn.setText('Transcribe')
        self._transcribe_btn.setEnabled(True)
