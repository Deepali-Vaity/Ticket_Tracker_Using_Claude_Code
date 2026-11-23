"""Shared test setup.

TICKET_DB_PATH must be set BEFORE database.py / app.py are imported, because
database.py reads it at import time. This keeps tests away from data/tickets.db.
"""

import os
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="ticket_tests_")
os.environ["TICKET_DB_PATH"] = os.path.join(_TEST_DB_DIR, "test_tickets.db")

import pytest  # noqa: E402

import app as app_module  # noqa: E402
import database  # noqa: E402
import models  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    """Start every test with an empty tickets table."""
    assert str(database.DB_PATH).startswith(_TEST_DB_DIR), "tests must use the temp DB"
    database.init_db()
    conn = database.get_connection()
    with conn:
        conn.execute("DELETE FROM tickets")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'tickets'")
    conn.close()
    yield


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture
def make_ticket():
    """Create a ticket and return its id."""
    def _make(title="Printer jam", description="Paper stuck", priority="Medium",
              status=None, engineer=None):
        ticket_id = models.create_ticket(title, description, priority, engineer)
        if status:
            models.update_status(ticket_id, status)
        return ticket_id
    return _make
