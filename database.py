"""Database helpers for the IT Helpdesk Ticket Tracker.

Responsibilities:
  * Provide a SQLite connection (rows behave like dictionaries).
  * Create the schema on first run.
  * Optionally load sample data:  python database.py --seed
"""

import os
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# The path can be overridden with an environment variable (handy for tests).
DB_PATH = Path(os.environ.get("TICKET_DB_PATH", BASE_DIR / "data" / "tickets.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    priority    TEXT NOT NULL CHECK (priority IN ('Low', 'Medium', 'High')),
    status      TEXT NOT NULL DEFAULT 'Open'
                CHECK (status IN ('Open', 'In Progress', 'Closed')),
    created_at  TEXT NOT NULL,
    assigned_engineer TEXT
);
"""

# (title, description, priority, status, created_at, assigned_engineer)
SAMPLE_TICKETS = [
    ("Cannot connect to VPN",
     "VPN client shows 'authentication failed' since this morning.",
     "High", "Open", "2026-11-18 09:15:00", "Alex Morgan"),
    ("Printer on floor 3 is offline",
     "The shared printer does not respond. Paper and toner are fine.",
     "Medium", "In Progress", "2026-11-18 11:40:00", "Sam Patel"),
    ("Request: install Visual Studio Code",
     "Need VS Code installed on my laptop for the new project.",
     "Low", "Open", "2026-11-19 14:05:00", None),
    ("Laptop battery drains quickly",
     "Battery lasts about 40 minutes on a full charge.",
     "Medium", "Open", "2026-11-19 16:30:00", None),
    ("Password reset for email account",
     "Locked out after too many attempts.",
     "High", "Closed", "2026-11-20 08:50:00", "Alex Morgan"),
    ("Monitor flickers intermittently",
     "External monitor flickers every few minutes. Cable already replaced.",
     "Low", "In Progress", "2026-11-20 13:20:00", "Sam Patel"),
    ("Shared drive access denied",
     "Cannot open the Finance shared folder since the permissions update.",
     "High", "In Progress", "2026-11-21 10:10:00", "Alex Morgan"),
    ("Wi-Fi drops in meeting room B",
     "Connection drops during video calls.",
     "Medium", "Closed", "2026-11-21 15:45:00", "Jamie Lee"),
]


def get_connection():
    """Open a new connection. Callers are responsible for closing it."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the tickets table if needed and upgrade older databases."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        # CREATE TABLE IF NOT EXISTS does not change an existing table, so add
        # columns introduced later. Existing rows get NULL (unassigned).
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tickets)")]
        if "assigned_engineer" not in columns:
            conn.execute("ALTER TABLE tickets ADD COLUMN assigned_engineer TEXT")


def seed_sample_data():
    """Insert sample tickets, but only if the table is empty."""
    init_db()
    conn = get_connection()
    try:
        with conn:
            count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            if count:
                return 0
            conn.executemany(
                "INSERT INTO tickets "
                "(title, description, priority, status, created_at, assigned_engineer) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                SAMPLE_TICKETS,
            )
            return len(SAMPLE_TICKETS)
    finally:
        conn.close()


if __name__ == "__main__":
    if "--seed" in sys.argv:
        added = seed_sample_data()
        print(f"Added {added} sample tickets." if added
              else "Table already has data; nothing added.")
    else:
        init_db()
        print(f"Database ready at {DB_PATH}")
