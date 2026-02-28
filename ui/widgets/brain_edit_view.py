import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QLabel, QScrollArea, QFrame,
    QSizePolicy, QFileDialog, QMessageBox, QMenu
)
from PySide6.QtCore import Qt, Signal

import qtawesome as qta

from models import Brain, Question, Resource, ResourceType, IndexStatus
from services.database import Database, BrainRepository, QuestionRepository, ResourceRepository
from ui.styles import (
    STYLE_SHEET, TEXT_PRIMARY,
    TEXT_DIM, ACCENT_BG, ACCENT_BORDER, DANGER_BG, DANGER_BORDER
)
from ui.threads import IndexThread, EstimateThread


class QuestionEditRow(QFrame):
    deleted = Signal(object)
    changed = Signal()

    def __init__(self, question: Question, parent=None):
        super().__init__(parent)
        self.question = question
        self.setObjectName('questionRow')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(8)

        self._label = QLabel(question.text)
        self._label.setStyleSheet(f'color: {TEXT_PRIMARY};')
        self._label.setWordWrap(True)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._input = QLineEdit(question.text)
        self._input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._input.returnPressed.connect(self._finish_edit)
        self._input.hide()

        layout.addWidget(self._label, 1)
        layout.addWidget(self._input, 1)

        self._edit_btn = QPushButton()
        self._edit_btn.setObjectName('iconBtn')
        self._edit_btn.setIcon(qta.icon('mdi.pencil', color='#666'))
        self._edit_btn.setFixedSize(24, 24)
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_btn.clicked.connect(self._start_edit)
        layout.addWidget(self._edit_btn)

        delete_btn = QPushButton()
        delete_btn.setObjectName('iconBtn')
        delete_btn.setIcon(qta.icon('mdi.close', color='#666'))
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.deleted.emit(self.question))
        layout.addWidget(delete_btn)

    def _start_edit(self):
        self._label.hide()
        self._edit_btn.hide()
        self._input.setText(self._label.text())
        self._input.show()
        self._input.setFocus()
        self._input.selectAll()

    def _finish_edit(self):
        text = self._input.text().strip()
        if text:
            self.question.text = text
            self._label.setText(text)
            self.changed.emit()
        self._input.hide()
        self._label.show()
        self._edit_btn.show()


class ResourceRow(QFrame):
    removed = Signal(object)

    def __init__(self, resource: Resource, parent=None):
        super().__init__(parent)
        self.resource = resource
        self.setObjectName('questionRow')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(8)

        icon = 'mdi.folder' if resource.resource_type == ResourceType.FOLDER else 'mdi.file'
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon, color='#888').pixmap(16, 16))
        layout.addWidget(icon_label)

        name_label = QLabel(resource.name)
        name_label.setStyleSheet(f'color: {TEXT_PRIMARY};')
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(name_label, 1)

        if resource.resource_type == ResourceType.FOLDER:
            status_map = {
                IndexStatus.PENDING: ('Pending', TEXT_DIM),
                IndexStatus.INDEXING: ('Scanning...', '#6eb5ff'),
                IndexStatus.INDEXED: ('Ready', '#4CAF50'),
                IndexStatus.FAILED: ('Failed', '#ff6b6b'),
            }
            text, color = status_map[resource.index_status]
            status_label = QLabel(text)
            status_label.setStyleSheet(f'color: {color}; font-size: 11px;')
            layout.addWidget(status_label)

        delete_btn = QPushButton()
        delete_btn.setObjectName('iconBtn')
        delete_btn.setIcon(qta.icon('mdi.close', color='#666'))
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.removed.emit(self.resource))
        layout.addWidget(delete_btn)


class BrainEditView(QWidget):
    navigate_back = Signal()
    brain_saved = Signal(str)
    brain_deleted = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.brain_repo = BrainRepository(db)
        self.question_repo = QuestionRepository(db)
        self.resource_repo = ResourceRepository(db)
        self._brain = None
        self._is_new = False
        self._question_rows: list[QuestionEditRow] = []
        self._deleted_question_ids: list[str] = []

        self.setStyleSheet(STYLE_SHEET)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        back_btn = QPushButton()
        back_btn.setObjectName('iconBtn')
        back_btn.setIcon(qta.icon('mdi.arrow-left', color='#6eb5ff'))
        back_btn.clicked.connect(self.navigate_back.emit)
        header.addWidget(back_btn)
        back_label = QPushButton('\u2190 Back')
        back_label.setStyleSheet('background: transparent; border: none; color: #6eb5ff;')
        back_label.setCursor(Qt.CursorShape.PointingHandCursor)
        back_label.clicked.connect(self.navigate_back.emit)
        header.addWidget(back_label)
        header.addStretch()
        self._title = QLabel('Edit Brain')
        self._title.setStyleSheet('font-weight: 600; font-size: 14px; color: #e0e0e0;')
        header.addWidget(self._title)
        header.addStretch()
        header.addSpacing(60)
        layout.addLayout(header)

        layout.addWidget(QLabel('Name'))
        self._name_input = QLineEdit()
        layout.addWidget(self._name_input)

        layout.addWidget(QLabel('What should this brain focus on?'))
        self._desc_input = QTextEdit()
        self._desc_input.setMaximumHeight(80)
        self._desc_input.setPlaceholderText('Describe what this brain should help with...')
        layout.addWidget(self._desc_input)

        layout.addWidget(self._section_label('QUESTIONS'))

        self._questions_scroll = QScrollArea()
        self._questions_scroll.setWidgetResizable(True)
        self._questions_scroll.setMaximumHeight(160)
        self._questions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._questions_container = QWidget()
        self._questions_layout = QVBoxLayout(self._questions_container)
        self._questions_layout.setSpacing(6)
        self._questions_layout.setContentsMargins(0, 0, 0, 0)
        self._questions_layout.addStretch()
        self._questions_scroll.setWidget(self._questions_container)
        layout.addWidget(self._questions_scroll)

        add_q_btn = QPushButton('+ Add question')
        add_q_btn.setStyleSheet('background: transparent; border: none; color: #6eb5ff; text-align: left;')
        add_q_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_q_btn.clicked.connect(self._add_question)
        layout.addWidget(add_q_btn)

        layout.addWidget(self._section_label('FILES & FOLDERS'))

        self._resources_container = QWidget()
        self._resources_layout = QVBoxLayout(self._resources_container)
        self._resources_layout.setSpacing(6)
        self._resources_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._resources_container)

        add_r_btn = QPushButton('+ Add files or folders')
        add_r_btn.setStyleSheet('background: transparent; border: none; color: #6eb5ff; text-align: left;')
        add_r_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_r_btn.clicked.connect(self._add_resource)
        layout.addWidget(add_r_btn)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._delete_btn = QPushButton('Delete')
        self._delete_btn.setStyleSheet(f'background-color: {DANGER_BG}; border-color: {DANGER_BORDER};')
        self._delete_btn.clicked.connect(self._delete_brain)
        btn_row.addWidget(self._delete_btn)

        save_btn = QPushButton('Save')
        save_btn.setStyleSheet(f'background-color: {ACCENT_BG}; border-color: {ACCENT_BORDER};')
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def load_brain(self, brain_id: str):
        self._brain = self.brain_repo.get(brain_id)
        self._is_new = False
        self._title.setText('Edit Brain')
        self._delete_btn.setVisible(True)
        self._populate()

    def load_new(self):
        self._brain = Brain(name='', description='')
        self._is_new = True
        self._title.setText('Build Your Own')
        self._delete_btn.setVisible(False)
        self._populate()

    def _populate(self):
        self._name_input.setText(self._brain.name)
        self._desc_input.setPlainText(self._brain.description)
        self._deleted_question_ids = []
        self._load_questions()
        self._load_resources()

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName('sectionLabel')
        return label

    def _load_questions(self):
        self._question_rows = []
        while self._questions_layout.count() > 1:
            item = self._questions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._is_new or not self._brain:
            return

        questions = self.question_repo.get_by_brain(self._brain.id)
        for q in questions:
            self._insert_question_row(q)

    def _insert_question_row(self, question: Question):
        row = QuestionEditRow(question)
        row.deleted.connect(self._remove_question)
        self._question_rows.append(row)
        self._questions_layout.insertWidget(self._questions_layout.count() - 1, row)

    def _add_question(self):
        q = Question(
            brain_id=self._brain.id if self._brain else '',
            text='New question',
            position=len(self._question_rows)
        )
        self._insert_question_row(q)
        # Start editing immediately
        self._question_rows[-1]._start_edit()

    def _remove_question(self, question: Question):
        for row in self._question_rows:
            if row.question is question:
                self._question_rows.remove(row)
                row.deleteLater()
                if question.id:
                    self._deleted_question_ids.append(question.id)
                break

    def _load_resources(self):
        while self._resources_layout.count():
            item = self._resources_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._brain:
            return

        resources = self.resource_repo.get_by_brain(self._brain.id)
        for r in resources:
            row = ResourceRow(r)
            row.removed.connect(self._remove_resource)
            self._resources_layout.addWidget(row)

    def _remove_resource(self, resource: Resource):
        self.resource_repo.unlink_from_brain(resource.id, self._brain.id)
        self._load_resources()

    def _ensure_brain_saved(self):
        if not self._is_new:
            return
        self._brain.name = self._name_input.text().strip() or 'Unnamed Brain'
        self._brain.description = self._desc_input.toPlainText().strip()
        self.brain_repo.create(self._brain)
        self._is_new = False

    def _add_resource(self):
        menu = QMenu(self)
        menu.addAction('Add Files', self._add_files)
        menu.addAction('Add Folder', self._add_folder)
        btn = self.sender()
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Select Files')
        if not paths:
            return
        self._ensure_brain_saved()
        for path in paths:
            self._add_file_resource(path)
        self._load_resources()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder')
        if not folder:
            return
        self._ensure_brain_saved()
        self._add_folder_resource(folder)
        self._load_resources()

    def _add_folder_resource(self, path):
        resource = Resource(
            resource_type=ResourceType.FOLDER,
            name=os.path.basename(path),
            path=path,
            index_status=IndexStatus.PENDING
        )
        self.resource_repo.create(resource)
        self.resource_repo.link_to_brain(resource.id, self._brain.id)
        self._start_indexing(resource, path)

    def _add_file_resource(self, path):
        resource = Resource(
            resource_type=ResourceType.FILE,
            name=os.path.basename(path),
            path=path,
            index_status=IndexStatus.INDEXED
        )
        self.resource_repo.create(resource)
        self.resource_repo.link_to_brain(resource.id, self._brain.id)

    def _start_indexing(self, resource, folder):
        from services.scanner import FileScanner
        scanner = FileScanner()
        self._estimate_thread = EstimateThread(folder, scanner)
        self._estimate_thread.complete.connect(
            lambda bytes_, count, paths: self._on_estimate_done(resource, paths)
        )
        self._estimate_thread.start()

    def _on_estimate_done(self, resource, paths):
        self.resource_repo.update_index_status(resource.id, IndexStatus.INDEXING)
        self._load_resources()

        from services.embedder import Embedder
        embedder = Embedder()
        from services.scanner import FileScanner
        scanner = FileScanner()
        from services.database import RAGService
        rag = RAGService(self.db)

        self._index_thread = IndexThread(
            resource=resource, paths=paths,
            embedder=embedder, scanner=scanner, rag=rag
        )
        self._index_thread.complete.connect(
            lambda bytes_, count: self._on_index_done(resource, bytes_, count)
        )
        self._index_thread.start()

    def _on_index_done(self, resource, total_bytes, file_count):
        self.resource_repo.update_index_status(
            resource.id, IndexStatus.INDEXED,
            size_bytes=total_bytes, file_count=file_count
        )
        self._load_resources()

    def _save(self):
        self._brain.name = self._name_input.text().strip() or 'Unnamed Brain'
        self._brain.description = self._desc_input.toPlainText().strip()

        if self._is_new:
            self.brain_repo.create(self._brain)
        else:
            self.brain_repo.update(self._brain)

        for qid in self._deleted_question_ids:
            self.question_repo.delete(qid)

        existing = self.question_repo.get_by_brain(self._brain.id)
        existing_ids = {q.id for q in existing}

        for i, row in enumerate(self._question_rows):
            row.question.brain_id = self._brain.id
            row.question.position = i
            if row.question.id in existing_ids:
                self.question_repo.update(row.question)
            else:
                self.question_repo.create(row.question)

        self.brain_saved.emit(self._brain.id)

    def _delete_brain(self):
        brains = self.brain_repo.get_all()
        if len(brains) <= 1:
            QMessageBox.warning(self, 'Cannot Delete', 'You must have at least one brain.')
            return
        self.brain_repo.delete(self._brain.id)
        self.brain_deleted.emit()
