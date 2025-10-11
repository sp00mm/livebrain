from PySide6.QtCore import QThread, Signal


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

