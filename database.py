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
    created_at  TEXT NOT NULL
);
"""

# (title, description, priority, status, created_at)
SAMPLE_TICKETS = [
    ("Cannot connect to VPN",
     "VPN client shows 'authentication failed' since this morning.",
     "High", "Open", "2026-11-18 09:15:00"),
    ("Printer on floor 3 is offline",
     "The shared printer does not respond. Paper and toner are fine.",
     "Medium", "In Progress", "2026-11-18 11:40:00"),
    ("Request: install Visual Studio Code",
     "Need VS Code installed on my laptop for the new project.",
     "Low", "Open", "2026-11-19 14:05:00"),
    ("Laptop battery drains quickly",
     "Battery lasts about 40 minutes on a full charge.",
     "Medium", "Open", "2026-11-19 16:30:00"),
    ("Password reset for email account",
     "Locked out after too many attempts.",
     "High", "Closed", "2026-11-20 08:50:00"),
    ("Monitor flickers intermittently",
     "External monitor flickers every few minutes. Cable already replaced.",
     "Low", "In Progress", "2026-11-20 13:20:00"),
    ("Shared drive access denied",
     "Cannot open the Finance shared folder since the permissions update.",
     "High", "In Progress", "2026-11-21 10:10:00"),
    ("Wi-Fi drops in meeting room B",
     "Connection drops during video calls.",
     "Medium", "Closed", "2026-11-21 15:45:00"),
]


def get_connection():
    """Open a new connection. Callers are responsible for closing it."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the tickets table if it does not exist yet."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)


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
                "INSERT INTO tickets (title, description, priority, status, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
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
