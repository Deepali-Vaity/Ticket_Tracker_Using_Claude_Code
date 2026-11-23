"""Tests for the ticket-quality skill script (.claude/skills/ticket-quality/scripts)."""

import importlib.util
import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

import database

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / ".claude" / "skills" / "ticket-quality" / "scripts" / "ticket_quality.py"
)
_spec = importlib.util.spec_from_file_location("ticket_quality", SCRIPT)
tq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tq)

AS_OF = "2026-11-23"


def ticket(**overrides):
    base = {"ticket_id": "TCK-001", "title": "VPN down", "assignee": "Alex",
            "status": "Open", "priority": "High", "created": "2026-11-20"}
    base.update(overrides)
    return base


def write_json(tmp_path, tickets, name="tickets.json"):
    path = tmp_path / name
    path.write_text(json.dumps(tickets), encoding="utf-8")
    return path


def run(path, *extra, capsys):
    code = tq.main([str(path), "--as-of", AS_OF, *extra])
    return code, capsys.readouterr().out


def summary_row(output, check):
    line = next(l for l in output.splitlines() if l.startswith(f"| {check}"))
    return [cell.strip() for cell in line.strip("|").split("|")]


# ---- overall result --------------------------------------------------------

def test_clean_file_passes(tmp_path, capsys):
    path = write_json(tmp_path, [ticket(), ticket(ticket_id="TCK-002", status="Closed")])
    code, out = run(path, capsys=capsys)
    assert code == 0
    assert "**Result: PASS** (0 errors, 0 warnings)" in out
    assert out.rstrip().endswith("Read-only: no files were modified.")


# ---- duplicates ------------------------------------------------------------

def test_duplicate_ids_reported_with_rows(tmp_path, capsys):
    path = write_json(tmp_path, [ticket(), ticket(ticket_id="TCK-002"), ticket()])
    code, out = run(path, capsys=capsys)
    assert code == 1
    assert "- ID `TCK-001` used by rows 1, 3" in out
    assert summary_row(out, "Duplicate or missing ticket IDs")[1:3] == ["FAIL", "1"]


def test_missing_id_reported(tmp_path, capsys):
    path = write_json(tmp_path, [ticket(ticket_id="  ")])
    _, out = run(path, capsys=capsys)
    assert "- Row 1 has no ticket ID" in out


# ---- orphans ---------------------------------------------------------------

@pytest.mark.parametrize("value", [None, "", "   ", "N/A", "none", "TBD"])
def test_orphan_values(tmp_path, capsys, value):
    path = write_json(tmp_path, [ticket(assignee=value)])
    _, out = run(path, capsys=capsys)
    assert summary_row(out, "Orphan tickets")[1:3] == ["FAIL", "1"]


def test_orphan_when_assignee_key_absent(tmp_path, capsys):
    raw = ticket()
    del raw["assignee"]
    _, out = run(write_json(tmp_path, [raw]), capsys=capsys)
    assert summary_row(out, "Orphan tickets")[1:3] == ["FAIL", "1"]


def test_assignee_field_name_variants_accepted(tmp_path, capsys):
    raw = ticket()
    raw["assigned_engineer"] = raw.pop("assignee")
    _, out = run(write_json(tmp_path, [raw]), capsys=capsys)
    assert summary_row(out, "Orphan tickets")[1:3] == ["PASS", "0"]


# ---- invalid values --------------------------------------------------------

def test_invalid_status_with_hint_and_missing(tmp_path, capsys):
    path = write_json(tmp_path, [
        ticket(ticket_id="1", status="in_progress"),
        ticket(ticket_id="2", status="Done"),
        ticket(ticket_id="3", status=""),
    ])
    _, out = run(path, capsys=capsys)
    assert '- `1`: found "in_progress" (did you mean "In Progress"?)' in out
    assert '- `2`: found "Done"' in out
    assert "- `3`: found (missing)" in out
    assert summary_row(out, "Invalid status values")[1:3] == ["FAIL", "3"]


def test_invalid_priority(tmp_path, capsys):
    path = write_json(tmp_path, [ticket(priority="Urgent"), ticket(ticket_id="2", priority="Critical")])
    _, out = run(path, capsys=capsys)
    assert summary_row(out, "Invalid priority values")[1:3] == ["FAIL", "1"]
    assert '- `TCK-001`: found "Urgent"' in out
    assert '`TCK-002`: found "Critical"' not in out  # Critical is valid in the extended profile


# ---- counts ----------------------------------------------------------------

def test_counts_include_zeros_and_total(tmp_path, capsys):
    path = write_json(tmp_path, [
        ticket(ticket_id="1", status="Open", priority="High"),
        ticket(ticket_id="2", status="Open", priority="Low"),
        ticket(ticket_id="3", status="Closed", priority="Low"),
        ticket(ticket_id="4", status="Weird", priority="Odd"),
    ])
    _, out = run(path, capsys=capsys)
    for row in ("| Open | 2 |", "| In Progress | 0 |", "| Resolved | 0 |", "| Closed | 1 |",
                "| Low | 2 |", "| Medium | 0 |", "| High | 1 |", "| Critical | 0 |"):
        assert row in out
    assert out.count("| Invalid or missing | 1 |") == 2
    assert out.count("| **Total** | 4 |") == 2


# ---- stale -----------------------------------------------------------------

def test_stale_boundary_is_strictly_more_than_30_days(tmp_path, capsys):
    path = write_json(tmp_path, [
        ticket(ticket_id="1", created="2026-10-24"),  # exactly 30 days: not stale
        ticket(ticket_id="2", created="2026-10-23"),  # 31 days: stale
    ])
    _, out = run(path, capsys=capsys)
    assert "- `2`: VPN down | status Open | 31 days old" in out
    assert "`1`: VPN down | status Open" not in out
    assert summary_row(out, "Stale tickets")[1:3] == ["WARN", "1"]


def test_resolved_and_closed_are_never_stale(tmp_path, capsys):
    path = write_json(tmp_path, [
        ticket(ticket_id="1", status="Closed", created="2025-01-01"),
        ticket(ticket_id="2", status="Resolved", created="2025-01-01"),
    ])
    code, out = run(path, capsys=capsys)
    assert code == 0
    assert summary_row(out, "Stale tickets")[1:3] == ["PASS", "0"]


def test_stale_sorted_oldest_first_and_custom_threshold(tmp_path, capsys):
    path = write_json(tmp_path, [
        ticket(ticket_id="1", created="2026-11-10"),
        ticket(ticket_id="2", created="2026-11-01"),
    ])
    _, out = run(path, "--stale-days", "10", capsys=capsys)
    assert out.index("`2`: VPN down") < out.index("`1`: VPN down")


def test_unreadable_created_date_is_warning(tmp_path, capsys):
    path = write_json(tmp_path, [ticket(created="19/11/2026"), ticket(ticket_id="2", created=None)])
    code, out = run(path, capsys=capsys)
    assert code == 1
    assert "**Result: PASS WITH WARNINGS**" in out
    assert summary_row(out, "Unreadable created dates")[1:3] == ["WARN", "2"]


def test_datetime_created_values_accepted(tmp_path, capsys):
    path = write_json(tmp_path, [ticket(created="2026-10-01 09:15:00")])
    _, out = run(path, capsys=capsys)
    assert "53 days old" in out


# ---- determinism -----------------------------------------------------------

def test_output_is_deterministic_and_order_independent(tmp_path, capsys):
    rows = [ticket(ticket_id=str(i), status=s, created=f"2026-10-{i + 1:02d}")
            for i, s in enumerate(["Open", "Closed", "Bad", "Open", "In Progress"], start=1)]
    first = run(write_json(tmp_path, rows, "a.json"), capsys=capsys)[1]
    second = run(write_json(tmp_path, rows, "a2.json"), capsys=capsys)[1]
    shuffled = run(write_json(tmp_path, list(reversed(rows)), "b.json"), capsys=capsys)[1]

    def body(text):  # the Source line differs by file name; rows differ by position
        return [l for l in text.splitlines() if l.startswith("| ") and "row" not in l]
    assert first.replace("a.json", "X") == second.replace("a2.json", "X")
    assert sorted(body(first)) == sorted(body(shuffled))


# ---- profiles and formats ---------------------------------------------------

def make_db(tmp_path, rows):
    path = tmp_path / "t.db"
    conn = sqlite3.connect(path)
    conn.executescript(database.SCHEMA)
    conn.executemany(
        "INSERT INTO tickets (title, description, priority, status, created_at, assigned_engineer) "
        "VALUES (?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    return path


def test_app_database_uses_app_profile(tmp_path, capsys):
    path = make_db(tmp_path, [("A", "d", "High", "Open", "2026-11-20 10:00:00", "Alex"),
                              ("B", "d", "Low", "Closed", "2026-11-01 10:00:00", None)])
    code, out = run(path, capsys=capsys)
    assert "- Profile: app" in out and "| Resolved |" not in out
    assert "- Tickets analysed: 2" in out
    assert "- `2`" in out  # orphan
    assert code == 1


def test_profile_override(tmp_path, capsys):
    path = make_db(tmp_path, [("A", "d", "High", "Open", "2026-11-20 10:00:00", "Alex")])
    _, out = run(path, "--profile", "extended", capsys=capsys)
    assert "- Profile: extended" in out and "| Resolved | 0 |" in out


def test_csv_input(tmp_path, capsys):
    path = tmp_path / "t.csv"
    path.write_text("ID,Title,Owner,State,Priority,Created\n"
                    "1,A,Sam,Open,Medium,2026-11-20\n1,B,,Open,Medium,2026-11-20\n", encoding="utf-8")
    code, out = run(path, capsys=capsys)
    assert code == 1
    assert "- ID `1` used by rows 1, 2" in out
    assert "### Orphan tickets (no assignee)\n- `1` (row 2)\n" in out  # which duplicate is unassigned


def test_json_object_with_tickets_key(tmp_path, capsys):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"tickets": [ticket()]}), encoding="utf-8")
    code, out = run(path, capsys=capsys)
    assert code == 0 and "- Tickets analysed: 1" in out


# ---- read-only and errors ---------------------------------------------------

def test_database_is_not_modified(tmp_path, capsys):
    path = make_db(tmp_path, [("A", "d", "High", "Open", "2026-11-20 10:00:00", "Alex")])
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    run(path, capsys=capsys)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_missing_file_errors_and_is_not_created(tmp_path, capsys):
    path = tmp_path / "nope.db"
    assert tq.main([str(path)]) == 2
    assert "File not found" in capsys.readouterr().err
    assert not path.exists()


def test_bad_json_and_bad_type_and_bad_date(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert tq.main([str(bad)]) == 2
    txt = tmp_path / "t.txt"
    txt.write_text("x", encoding="utf-8")
    assert tq.main([str(txt)]) == 2
    good = write_json(tmp_path, [ticket()])
    assert tq.main([str(good), "--as-of", "yesterday"]) == 2
    assert tq.main([str(good), "--stale-days", "-1"]) == 2


def test_db_without_tickets_table_errors(tmp_path):
    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    assert tq.main([str(path)]) == 2


def test_runs_as_a_command_line_script(tmp_path):
    path = write_json(tmp_path, [ticket()])
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), "--as-of", AS_OF],
        capture_output=True, text=True, encoding="utf-8", check=False)
    assert result.returncode == 0
    assert "# Ticket Quality Report" in result.stdout
    assert date.fromisoformat(AS_OF).isoformat() in result.stdout
