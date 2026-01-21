import sys
import json
import os
from PySide6.QtWidgets import QApplication
from ui import MainWindow


def get_version():
    version_file = os.path.join(os.path.dirname(__file__), 'version.json')
    with open(version_file, 'r') as f:
        return json.load(f)['version']


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LiveBrain")
    app.setApplicationVersion(get_version())
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

