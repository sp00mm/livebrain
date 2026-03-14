import os
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import sys
import json
from PySide6.QtWidgets import QApplication
from menubar import MenuBarApp
from services.crash_reporter import install as install_crash_reporter


def get_version():
    version_file = os.path.join(os.path.dirname(__file__), 'version.json')
    with open(version_file, 'r') as f:
        return json.load(f)['version']


def main():
    install_crash_reporter()

    app = QApplication(sys.argv)
    app.setApplicationName('Livebrain')
    app.setApplicationVersion(get_version())
    app.setQuitOnLastWindowClosed(False)

    menubar_app = MenuBarApp()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
