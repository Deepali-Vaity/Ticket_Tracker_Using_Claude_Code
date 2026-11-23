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
