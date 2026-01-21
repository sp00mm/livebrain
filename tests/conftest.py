"""
Pytest configuration and fixtures for Livebrain tests.
"""

import os
import sys
import tempfile

import pytest

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import Database


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    db_path = os.path.join(tempfile.gettempdir(), f"livebrain_test_{os.getpid()}.db")

    # Clean up any existing test db
    if os.path.exists(db_path):
        os.remove(db_path)

    database = Database(db_path)
    database.initialize_schema()

    yield database

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
