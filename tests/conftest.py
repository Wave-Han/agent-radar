"""Shared pytest fixtures."""
import sqlite3

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """A fresh on-disk SQLite connection for storage tests."""
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
