import os
from PyPDF2 import PdfReader


class FileScanner:
    TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv', '.log'}

    def scan_directory(self, directory):
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        return files

    def estimate_folder_size(self, directory: str) -> tuple[int, int, list[str]]:
        total_bytes = 0
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.TEXT_EXTENSIONS or ext == '.pdf':
                    filepath = os.path.join(root, filename)
                    total_bytes += os.path.getsize(filepath)
                    files.append(filepath)
        return total_bytes, len(files), files

    def extract_text(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.pdf':
            return self._extract_pdf(filepath)
        elif ext in self.TEXT_EXTENSIONS:
            return self._extract_text_file(filepath)
        return None

    def _extract_text_file(self, filepath):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def _extract_pdf(self, filepath):
        reader = PdfReader(filepath)
        text = ''
        for page in reader.pages:
            text += page.extract_text() + '\n'
        return text

