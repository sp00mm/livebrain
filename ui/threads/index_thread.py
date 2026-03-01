import os
from PySide6.QtCore import QThread, Signal

from models import ResourceType


class EstimateThread(QThread):
    complete = Signal(int, int, list)  # (bytes, count, paths)

    def __init__(self, path, scanner):
        super().__init__()
        self.path = path
        self.scanner = scanner

    def run(self):
        total_bytes, file_count, paths = self.scanner.estimate_folder_size(self.path)
        self.complete.emit(total_bytes, file_count, paths)


class IndexThread(QThread):
    file_progress = Signal(str, int, int)  # (filename, current, total)
    complete = Signal(int, int)  # (bytes, count)

    def __init__(self, resource, paths, embedder, scanner, rag):
        super().__init__()
        self.resource = resource
        self.paths = paths
        self.embedder = embedder
        self.scanner = scanner
        self.rag = rag
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total_bytes = 0
        for i, filepath in enumerate(self.paths):
            if self._cancelled:
                return
            self.file_progress.emit(os.path.basename(filepath), i + 1, len(self.paths))
            total_bytes += os.path.getsize(filepath)
            segments = self.scanner.extract_text_with_meta(filepath)
            segments = [(text, meta) for text, meta in segments if text and text.strip()]
            if segments:
                self.rag.index_text_with_meta(
                    resource_id=self.resource.id,
                    filepath=filepath,
                    segments=segments,
                    embedding_fn=lambda t: self.embedder.embed(t, is_query=False)
                )

        self.complete.emit(total_bytes, len(self.paths))
