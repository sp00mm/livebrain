import os
import webbrowser
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QLabel,
    QMessageBox, QProgressDialog, QGroupBox
)
from PySide6.QtCore import Qt

from services import Embedder, FileScanner, Database, RAGService, Updater, AudioService
from models import Brain, Session, TranscriptEntry, SpeakerType
from ui.threads import ModelDownloadThread, IndexThread


class MainWindow(QMainWindow):    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveBrain v1.0.0")
        self.setGeometry(100, 100, 800, 600)
        
        self.scanner = FileScanner()
        self.db = Database()
        self.db.initialize_schema()
        self.rag = RAGService(self.db)
        self.updater = Updater()
        self.audio_service = AudioService(self.db)
        self.embedder = None
        self._default_brain = None
        self._final_transcripts = []
        self._partial_text = ''

        self.setup_ui()
        self.check_models_and_initialize()
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Models download button at the top
        self.models_btn = QPushButton("⬇️ Download AI Models (Required for Search)")
        self.models_btn.clicked.connect(self.download_models)
        self.models_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "padding: 10px; font-weight: bold; }"
        )
        self.models_btn.setVisible(False)
        layout.addWidget(self.models_btn)
        
        # Directory selection
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Directory path")
        layout.addWidget(self.dir_input)
        
        select_btn = QPushButton("Select Directory")
        select_btn.clicked.connect(self.select_directory)
        layout.addWidget(select_btn)
        
        index_btn = QPushButton("Index Directory")
        index_btn.clicked.connect(self.index_directory)
        layout.addWidget(index_btn)
        
        # Status display
        self.status = QTextEdit()
        self.status.setMaximumHeight(150)
        self.status.setReadOnly(True)
        layout.addWidget(self.status)

        # Audio recording section
        audio_group = QGroupBox('Audio Recording')
        audio_layout = QVBoxLayout(audio_group)

        audio_controls = QHBoxLayout()
        self.record_btn = QPushButton('Start Recording')
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setStyleSheet(
            'QPushButton { background-color: #2196F3; color: white; padding: 8px; font-weight: bold; }'
        )
        audio_controls.addWidget(self.record_btn)

        self.recording_status = QLabel('Stopped')
        audio_controls.addWidget(self.recording_status)
        audio_controls.addStretch()
        audio_layout.addLayout(audio_controls)

        self.transcript_display = QTextEdit()
        self.transcript_display.setReadOnly(True)
        self.transcript_display.setPlaceholderText('Transcript will appear here...')
        self.transcript_display.setMaximumHeight(200)
        audio_layout.addWidget(self.transcript_display)

        layout.addWidget(audio_group)

        # Search interface
        layout.addWidget(QLabel('Search:'))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search query")
        self.search_input.returnPressed.connect(self.search)
        layout.addWidget(self.search_input)
        
        search_btn = QPushButton("Find")
        search_btn.clicked.connect(self.search)
        layout.addWidget(search_btn)
        
        # Results display
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        layout.addWidget(self.results)
    
    def check_models_and_initialize(self):
        """Check if AI models exist and initialize or prompt for download."""
        model_dir = Embedder.get_model_dir()
        model_file = os.path.join(model_dir, "onnx", "model_q4.onnx")
        
        if not os.path.exists(model_file):
            # Show the download button in the UI
            self.models_btn.setVisible(True)
            self.status.append("⚠️ AI models not found. Click the button above to download them (~160MB).")
            self.status.append(f"Models will be saved to: {model_dir}")
            self.status.append("")
            self.status.append("💡 You can still browse the app while models are downloading.")
        else:
            # Models exist, hide the button and initialize
            self.models_btn.setVisible(False)
            self.initialize_embedder()
            self.check_for_updates()
    
    def download_models(self):
        """Start downloading AI models in a background thread."""
        model_dir = os.path.dirname(Embedder.get_model_dir())
        
        self.progress_dialog = QProgressDialog("Downloading models...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.canceled.connect(self.cancel_download)
        
        self.download_thread = ModelDownloadThread(self.updater, model_dir)
        self.download_thread.progress.connect(self.update_download_progress)
        self.download_thread.finished.connect(self.download_complete)
        self.download_thread.start()
        
        self.progress_dialog.show()
    
    def update_download_progress(self, percent, downloaded, total):
        """Update the download progress dialog."""
        self.progress_dialog.setValue(percent)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        self.progress_dialog.setLabelText(
            f"Downloading models... {mb_downloaded:.1f} MB / {mb_total:.1f} MB"
        )
    
    def cancel_download(self):
        """Handle download cancellation."""
        if hasattr(self, 'download_thread'):
            self.download_thread.terminate()
        self.status.append("Download canceled. You can retry by clicking the download button.")
        QMessageBox.information(
            self, 
            "Download Canceled", 
            "You can download the models later using the button at the top."
        )
    
    def download_complete(self, success, error):
        """Handle download completion or failure."""
        self.progress_dialog.close()
        
        if success:
            self.models_btn.setVisible(False)
            self.status.append("✅ Models downloaded successfully!")
            QMessageBox.information(self, "Download Complete", "Models downloaded successfully!")
            self.initialize_embedder()
            self.check_for_updates()
        else:
            self.status.append(f"❌ Download failed: {error}")
            QMessageBox.critical(
                self, 
                "Download Failed", 
                f"Failed to download models: {error}\n\n"
                "You can try again by clicking the download button."
            )
    
    def initialize_embedder(self):
        """Initialize the embedder service."""
        self.embedder = Embedder()
        # Create or get default brain for indexing
        from services import BrainRepository
        brain_repo = BrainRepository(self.db)
        brains = brain_repo.get_all()
        if brains:
            self._default_brain = brains[0]
        else:
            self._default_brain = brain_repo.create(Brain(name="Default"))
    
    def check_for_updates(self):
        """Check for application updates."""
        update_info = self.updater.check_for_updates()
        if update_info["available"]:
            reply = QMessageBox.question(
                self,
                "Update Available",
                f"Version {update_info['version']} is available. Download now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                webbrowser.open(update_info["url"])
    
    def select_directory(self):
        """Open a directory selection dialog."""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.dir_input.setText(directory)
    
    def index_directory(self):
        """Start indexing the selected directory in a background thread."""
        if not self.embedder:
            QMessageBox.warning(self, "Not Ready", "Please wait for models to download.")
            return
        
        directory = self.dir_input.text()
        if not directory:
            return
        
        self.status.clear()
        self.status.append("Starting indexing...")
        
        self.thread = IndexThread(directory, self.embedder, self.scanner, self.rag, self._default_brain.id)
        self.thread.progress.connect(lambda msg: self.status.append(msg))
        self.thread.finished.connect(lambda: self.status.append("Indexing complete"))
        self.thread.start()
    
    def search(self):
        """Perform a semantic search on indexed documents."""
        if not self.embedder:
            QMessageBox.warning(self, "Not Ready", "Please wait for models to download.")
            return

        query = self.search_input.text()
        if not query:
            return

        self.results.clear()
        embedding = self.embedder.embed(query, is_query=True)
        results = self.rag.search(embedding, brain_id=self._default_brain.id if self._default_brain else None)

        for result in results:
            self.results.append(f"Score: {result['similarity']:.4f}")
            self.results.append(f"File: {result['chunk'].filepath}")
            self.results.append(f"Preview: {result['chunk'].text[:200]}...")
            self.results.append("-" * 80)

    def toggle_recording(self):
        if self.audio_service.is_recording():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        session = Session(name='Recording Session')
        self.audio_service.start_session(session, self._on_transcript)
        self.record_btn.setText('Stop Recording')
        self.record_btn.setStyleSheet(
            'QPushButton { background-color: #f44336; color: white; padding: 8px; font-weight: bold; }'
        )
        self.recording_status.setText('Recording...')
        self._final_transcripts = []
        self._partial_text = ''
        self.transcript_display.clear()

    def stop_recording(self):
        self.audio_service.stop_session()
        self.record_btn.setText('Start Recording')
        self.record_btn.setStyleSheet(
            'QPushButton { background-color: #2196F3; color: white; padding: 8px; font-weight: bold; }'
        )
        self.recording_status.setText('Stopped')

    def _on_transcript(self, entry: TranscriptEntry, is_final: bool):
        speaker = 'You' if entry.speaker == SpeakerType.USER else 'Other'
        if is_final:
            self._final_transcripts.append(f'{speaker}: {entry.text}')
            self._partial_text = ''
        else:
            self._partial_text = f'{speaker}: {entry.text}...'
        self._update_transcript_display()

    def _update_transcript_display(self):
        lines = self._final_transcripts[-10:]
        if self._partial_text:
            lines = lines + [self._partial_text]
        self.transcript_display.setPlainText('\n'.join(lines))

