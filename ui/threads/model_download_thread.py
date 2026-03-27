from PySide6.QtCore import QThread, Signal


class ModelDownloadThread(QThread):

    progress = Signal(int, int, int)
    finished = Signal(bool, str)

    def __init__(self, updater, dest_dir, download_fn=None):
        super().__init__()
        self.updater = updater
        self.dest_dir = dest_dir
        self._download_fn = download_fn or updater.download_models

    def run(self):
        try:
            self._download_fn(
                self.dest_dir,
                lambda percent, downloaded, total: self.progress.emit(percent, downloaded, total)
            )
            self.finished.emit(True, '')
        except Exception as e:
            self.finished.emit(False, str(e))
