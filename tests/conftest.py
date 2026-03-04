import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import Database


@pytest.fixture
def db():
    db_path = os.path.join(tempfile.gettempdir(), f'livebrain_test_{os.getpid()}.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    database = Database(db_path)
    database.initialize_schema()
    yield database
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope='session')
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication([])
