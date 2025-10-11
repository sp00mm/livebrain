import os
from PyPDF2 import PdfReader

class FileScanner:
    TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv', '.log'}
    
    def scan_directory(self, directory):
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                files.append(filepath)
        return files
    
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
        try:
            reader = PdfReader(filepath)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except:
            return None

