import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QPushButton, QLineEdit, QTextEdit, QFileDialog, QLabel, 
                               QMessageBox, QProgressDialog)
from PySide6.QtCore import QThread, Signal, Qt
from embedder import Embedder
from scanner import FileScanner
from storage import DocumentStorage
from updater import Updater

class ModelDownloadThread(QThread):
    progress = Signal(int, int, int)
    finished = Signal(bool, str)
    
    def __init__(self, updater, dest_dir):
        super().__init__()
        self.updater = updater
        self.dest_dir = dest_dir
    
    def run(self):
        try:
            self.updater.download_models(
                self.dest_dir,
                lambda percent, downloaded, total: self.progress.emit(percent, downloaded, total)
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))

class IndexThread(QThread):
    progress = Signal(str)
    finished = Signal()
    
    def __init__(self, directory, embedder, scanner, storage):
        super().__init__()
        self.directory = directory
        self.embedder = embedder
        self.scanner = scanner
        self.storage = storage
    
    def run(self):
        files = self.scanner.scan_directory(self.directory)
        self.progress.emit(f"Found {len(files)} files")
        
        for i, filepath in enumerate(files):
            text = self.scanner.extract_text(filepath)
            if text and text.strip():
                embedding = self.embedder.embed(text, is_query=False)
                self.storage.insert(filepath, text, embedding)
                self.progress.emit(f"Indexed {i+1}/{len(files)}: {filepath}")
        
        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LiveBrain v1.0.0")
        self.setGeometry(100, 100, 800, 600)
        
        self.scanner = FileScanner()
        self.storage = DocumentStorage()
        self.updater = Updater()
        self.embedder = None
        
        self.setup_ui()
        self.check_models_and_initialize()
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Directory path")
        layout.addWidget(self.dir_input)
        
        select_btn = QPushButton("Select Directory")
        select_btn.clicked.connect(self.select_directory)
        layout.addWidget(select_btn)
        
        index_btn = QPushButton("Index Directory")
        index_btn.clicked.connect(self.index_directory)
        layout.addWidget(index_btn)
        
        self.status = QTextEdit()
        self.status.setMaximumHeight(150)
        self.status.setReadOnly(True)
        layout.addWidget(self.status)
        
        layout.addWidget(QLabel("Search:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search query")
        self.search_input.returnPressed.connect(self.search)
        layout.addWidget(self.search_input)
        
        search_btn = QPushButton("Find")
        search_btn.clicked.connect(self.search)
        layout.addWidget(search_btn)
        
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        layout.addWidget(self.results)
    
    def check_models_and_initialize(self):
        model_dir = Embedder.get_model_dir()
        model_file = os.path.join(model_dir, "onnx", "model.onnx")
        
        if not os.path.exists(model_file):
            reply = QMessageBox.question(
                self,
                "Download Required",
                "Embedding models need to be downloaded (~600MB). Download now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.download_models()
            else:
                QMessageBox.warning(self, "Cannot Continue", "Models are required to run the app.")
                sys.exit(0)
        else:
            self.initialize_embedder()
            self.check_for_updates()
    
    def download_models(self):
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
        self.progress_dialog.setValue(percent)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        self.progress_dialog.setLabelText(f"Downloading models... {mb_downloaded:.1f} MB / {mb_total:.1f} MB")
    
    def cancel_download(self):
        if hasattr(self, 'download_thread'):
            self.download_thread.terminate()
        QMessageBox.warning(self, "Download Canceled", "Models are required to run the app.")
        sys.exit(0)
    
    def download_complete(self, success, error):
        self.progress_dialog.close()
        
        if success:
            QMessageBox.information(self, "Download Complete", "Models downloaded successfully!")
            self.initialize_embedder()
            self.check_for_updates()
        else:
            QMessageBox.critical(self, "Download Failed", f"Failed to download models: {error}")
            sys.exit(1)
    
    def initialize_embedder(self):
        self.embedder = Embedder()
        embedding_dim = len(self.embedder.embed("test"))
        self.storage.initialize(embedding_dim)
    
    def check_for_updates(self):
        update_info = self.updater.check_for_updates()
        if update_info["available"]:
            reply = QMessageBox.question(
                self,
                "Update Available",
                f"Version {update_info['version']} is available. Download now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                import webbrowser
                webbrowser.open(update_info["url"])
    
    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.dir_input.setText(directory)
    
    def index_directory(self):
        if not self.embedder:
            QMessageBox.warning(self, "Not Ready", "Please wait for models to download.")
            return
        
        directory = self.dir_input.text()
        if not directory:
            return
        
        self.status.clear()
        self.status.append("Starting indexing...")
        
        self.thread = IndexThread(directory, self.embedder, self.scanner, self.storage)
        self.thread.progress.connect(lambda msg: self.status.append(msg))
        self.thread.finished.connect(lambda: self.status.append("Indexing complete"))
        self.thread.start()
    
    def search(self):
        if not self.embedder:
            QMessageBox.warning(self, "Not Ready", "Please wait for models to download.")
            return
        
        query = self.search_input.text()
        if not query:
            return
        
        self.results.clear()
        embedding = self.embedder.embed(query, is_query=True)
        results = self.storage.search(embedding)
        
        for result in results:
            self.results.append(f"Score: {result['distance']:.4f}")
            self.results.append(f"File: {result['entity']['filepath']}")
            self.results.append(f"Preview: {result['entity']['text'][:200]}...")
            self.results.append("-" * 80)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

