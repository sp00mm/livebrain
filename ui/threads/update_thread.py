from PySide6.QtCore import QThread, Signal


class UpdateCheckThread(QThread):
    update_available = Signal(dict)

    def __init__(self, updater):
        super().__init__()
        self.updater = updater

    def run(self):
        result = self.updater.check_for_updates()
        if result.get('available'):
            self.update_available.emit(result)


class UpdateDownloadThread(QThread):
    finished = Signal(str)

    def __init__(self, updater, url):
        super().__init__()
        self.updater = updater
        self.url = url

    def run(self):
        path = self.updater.download_update(self.url)
        self.finished.emit(path)
