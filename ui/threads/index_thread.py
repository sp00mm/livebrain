from PySide6.QtCore import QThread, Signal


class IndexThread(QThread):
    progress = Signal(str)
    finished = Signal()

    def __init__(self, directory, embedder, scanner, rag, brain_id):
        super().__init__()
        self.directory = directory
        self.embedder = embedder
        self.scanner = scanner
        self.rag = rag
        self.brain_id = brain_id

    def run(self):
        files = self.scanner.scan_directory(self.directory)
        self.progress.emit(f"Found {len(files)} files")

        for i, filepath in enumerate(files):
            text = self.scanner.extract_text(filepath)
            if text and text.strip():
                self.rag.index_text(
                    brain_id=self.brain_id,
                    filepath=filepath,
                    text=text,
                    embedding_fn=lambda t: self.embedder.embed(t, is_query=False)
                )
                self.progress.emit(f"Indexed {i+1}/{len(files)}: {filepath}")

        self.finished.emit()

