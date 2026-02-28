from PySide6.QtCore import QThread, Signal


class UrlScrapeThread(QThread):
    complete = Signal(str)
    error = Signal(str)

    def __init__(self, url: str, template_service):
        super().__init__()
        self.url = url
        self._service = template_service

    def run(self):
        try:
            result = self._service.generate_from_url(self.url)
            self.complete.emit(result)
        except Exception as e:
            self.error.emit(str(e))
