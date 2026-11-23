"""Tests for the data layer (models.py)."""

import re
import sqlite3

import pytest

import database
import models


def test_create_ticket_defaults(make_ticket):
    ticket = models.get_ticket(make_ticket(priority="High"))
    assert ticket["status"] == "Open"
    assert ticket["priority"] == "High"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", ticket["created_at"])


def test_get_ticket_missing_returns_none():
    assert models.get_ticket(999) is None


def test_list_newest_first(make_ticket):
    first = make_ticket(title="first")
    second = make_ticket(title="second")
    ids = [t["id"] for t in models.list_tickets()]
    assert ids == [second, first]


@pytest.mark.parametrize("status", models.STATUSES)
def test_list_filter_by_status(make_ticket, status):
    for s in models.STATUSES:
        make_ticket(title=f"t-{s}", status=s)
    tickets = models.list_tickets(status)
    assert len(tickets) == 1
    assert tickets[0]["status"] == status


def test_list_invalid_status_returns_all(make_ticket):
    make_ticket()
    make_ticket(status="Closed")
    assert len(models.list_tickets("bogus")) == 2


def test_update_status_valid(make_ticket):
    ticket_id = make_ticket()
    assert models.update_status(ticket_id, "In Progress") is True
    assert models.get_ticket(ticket_id)["status"] == "In Progress"


def test_update_status_invalid_not_written(make_ticket):
    ticket_id = make_ticket()
    assert models.update_status(ticket_id, "Done") is False
    assert models.get_ticket(ticket_id)["status"] == "Open"


def test_update_status_unknown_ticket():
    assert models.update_status(999, "Closed") is False


def test_dashboard_counts_empty():
    counts = models.get_dashboard_counts()
    assert counts["total"] == 0
    assert counts["by_status"] == {"Open": 0, "In Progress": 0, "Closed": 0}
    assert counts["by_priority"] == {"Low": 0, "Medium": 0, "High": 0}


def test_dashboard_counts_populated(make_ticket):
    make_ticket(priority="High")
    make_ticket(priority="High", status="Closed")
    make_ticket(priority="Low", status="In Progress")
    counts = models.get_dashboard_counts()
    assert counts["total"] == 3
    assert counts["by_status"] == {"Open": 1, "In Progress": 1, "Closed": 1}
    assert counts["by_priority"] == {"Low": 1, "Medium": 0, "High": 2}


def test_special_characters_stored_as_text(make_ticket):
    nasty = "'; DROP TABLE tickets;--"
    ticket_id = make_ticket(title=nasty, description=nasty)
    assert models.get_ticket(ticket_id)["title"] == nasty
    assert len(models.list_tickets()) == 1  # table still exists


def test_db_rejects_bad_priority_and_status():
    conn = database.get_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO tickets (title, description, priority, status, created_at) "
                "VALUES ('t', 'd', 'Urgent', 'Open', '2026-01-01 00:00:00')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO tickets (title, description, priority, status, created_at) "
                "VALUES ('t', 'd', 'Low', 'Done', '2026-01-01 00:00:00')"
            )
    finally:
        conn.close()


# ---- assigned engineer -----------------------------------------------------

def test_create_with_and_without_engineer(make_ticket):
    assert models.get_ticket(make_ticket(engineer="Alex Morgan"))["assigned_engineer"] == "Alex Morgan"
    assert models.get_ticket(make_ticket())["assigned_engineer"] is None


def test_filter_by_engineer_case_insensitive(make_ticket):
    make_ticket(title="a", engineer="Alex Morgan")
    make_ticket(title="b", engineer="Sam Patel")
    titles = [t["title"] for t in models.list_tickets(engineer="alex morgan")]
    assert titles == ["a"]


def test_filter_unassigned(make_ticket):
    make_ticket(title="mine", engineer="Alex")
    make_ticket(title="nobody")
    titles = [t["title"] for t in models.list_tickets(engineer=models.UNASSIGNED)]
    assert titles == ["nobody"]


def test_filter_status_and_engineer_combined(make_ticket):
    make_ticket(title="match", engineer="Alex", status="Closed")
    make_ticket(title="wrong status", engineer="Alex")
    make_ticket(title="wrong engineer", engineer="Sam", status="Closed")
    titles = [t["title"] for t in models.list_tickets("Closed", "Alex")]
    assert titles == ["match"]


def test_list_engineers_distinct_sorted(make_ticket):
    make_ticket(engineer="sam")
    make_ticket(engineer="Alex")
    make_ticket(engineer="Sam")
    make_ticket()
    assert [n.lower() for n in models.list_engineers()] == ["alex", "sam"]


def test_update_engineer_assign_and_clear(make_ticket):
    ticket_id = make_ticket()
    assert models.update_engineer(ticket_id, "Alex") is True
    assert models.get_ticket(ticket_id)["assigned_engineer"] == "Alex"
    assert models.update_engineer(ticket_id, "") is True
    assert models.get_ticket(ticket_id)["assigned_engineer"] is None


def test_update_engineer_unknown_ticket():
    assert models.update_engineer(999, "Alex") is False


def test_engineer_filter_is_injection_safe(make_ticket):
    make_ticket(engineer="Alex")
    assert models.list_tickets(engineer="x' OR '1'='1") == []


def test_init_db_migrates_old_database(tmp_path, monkeypatch):
    old_path = tmp_path / "old.db"
    conn = sqlite3.connect(old_path)
    conn.executescript(
        "CREATE TABLE tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
        "description TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open', "
        "created_at TEXT NOT NULL);"
        "INSERT INTO tickets (title, description, priority, status, created_at) "
        "VALUES ('old', 'row', 'Low', 'Open', '2026-01-01 00:00:00');"
    )
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", old_path)

    database.init_db()
    database.init_db()  # running twice must be safe

    conn = database.get_connection()
    try:
        row = conn.execute("SELECT title, assigned_engineer FROM tickets").fetchone()
    finally:
        conn.close()
    assert row["title"] == "old"
    assert row["assigned_engineer"] is None


# ---- priority filter -------------------------------------------------------

@pytest.mark.parametrize("priority", models.PRIORITIES)
def test_list_filter_by_priority(make_ticket, priority):
    for p in models.PRIORITIES:
        make_ticket(title=f"t-{p}", priority=p)
    tickets = models.list_tickets(priority=priority)
    assert [t["priority"] for t in tickets] == [priority]


def test_list_invalid_priority_returns_all(make_ticket):
    make_ticket(priority="Low")
    make_ticket(priority="High")
    assert len(models.list_tickets(priority="Urgent")) == 2


def test_filter_priority_with_status_and_engineer(make_ticket):
    make_ticket(title="hit", priority="High", engineer="Alex", status="Closed")
    make_ticket(title="wrong priority", priority="Low", engineer="Alex", status="Closed")
    make_ticket(title="wrong status", priority="High", engineer="Alex")
    make_ticket(title="wrong engineer", priority="High", engineer="Sam", status="Closed")
    titles = [t["title"] for t in models.list_tickets("Closed", "Alex", "High")]
    assert titles == ["hit"]
