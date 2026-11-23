"""Data-access functions for tickets.

All SQL lives here so that app.py only deals with web concerns.
Every query is parameterised (no string formatting) to prevent SQL injection.
"""

from datetime import datetime

from database import get_connection

PRIORITIES = ("Low", "Medium", "High")
STATUSES = ("Open", "In Progress", "Closed")


def create_ticket(title, description, priority):
    """Insert a new ticket (status 'Open') and return its id."""
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO tickets (title, description, priority, status, created_at) "
                "VALUES (?, ?, ?, 'Open', ?)",
                (title, description, priority, created_at),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_ticket(ticket_id):
    """Return one ticket as a Row, or None if it does not exist."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
    finally:
        conn.close()


def list_tickets(status=None):
    """Return tickets newest first, optionally filtered by status."""
    query = "SELECT * FROM tickets"
    params = ()
    if status in STATUSES:
        query += " WHERE status = ?"
        params = (status,)
    query += " ORDER BY created_at DESC, id DESC"
    conn = get_connection()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def update_status(ticket_id, new_status):
    """Change a ticket's status. Returns True if a ticket was updated."""
    if new_status not in STATUSES:
        return False
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE tickets SET status = ? WHERE id = ?", (new_status, ticket_id)
            )
            return cursor.rowcount > 0
    finally:
        conn.close()


def _count_by(column, allowed):
    """Return {value: count} for a column, including zero counts."""
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {column} AS value, COUNT(*) AS n FROM tickets GROUP BY {column}"
        ).fetchall()
    finally:
        conn.close()
    counts = {value: 0 for value in allowed}
    counts.update({row["value"]: row["n"] for row in rows})
    return counts


def get_dashboard_counts():
    """Return totals used by the dashboard page."""
    by_status = _count_by("status", STATUSES)
    by_priority = _count_by("priority", PRIORITIES)
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "by_priority": by_priority,
    }
