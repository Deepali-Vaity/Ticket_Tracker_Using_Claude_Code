#!/usr/bin/env python3
"""Read-only ticket data-quality report (standard library only).

Usage:
    python ticket_quality.py [PATH] [--as-of YYYY-MM-DD] [--stale-days 30]
                             [--profile app|extended]

PATH may be a SQLite database (.db/.sqlite/.sqlite3), a JSON file or a CSV file.
Default PATH is data/tickets.db (relative to the current directory).

The report is deterministic: the same input, --as-of date and options always give
byte-identical output. The script never writes to any file.

Exit codes: 0 = no findings, 1 = findings reported, 2 = input error.
"""

import argparse
import csv
import json
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

PROFILES = {
    # Matches the Flask app's CHECK constraints (default for SQLite files).
    "app": {
        "statuses": ("Open", "In Progress", "Closed"),
        "priorities": ("Low", "Medium", "High"),
    },
    # Matches the /review-ticket lifecycle (default for JSON and CSV files).
    "extended": {
        "statuses": ("Open", "In Progress", "Resolved", "Closed"),
        "priorities": ("Low", "Medium", "High", "Critical"),
    },
}
RESOLVED_STATUSES = ("Resolved", "Closed")
PLACEHOLDERS = {"", "null", "none", "n/a", "na", "tbd"}
DB_SUFFIXES = {".db", ".sqlite", ".sqlite3"}

# Normalised field name (lower case, letters and digits only) -> canonical field.
FIELD_ALIASES = {
    "id": "id", "ticketid": "id", "key": "id",
    "title": "title", "summary": "title", "subject": "title",
    "assignee": "assignee", "assignedto": "assignee",
    "assignedengineer": "assignee", "owner": "assignee",
    "status": "status", "state": "status",
    "priority": "priority",
    "created": "created", "createdat": "created", "createddate": "created",
    "createdon": "created", "opened": "created",
}


class InputError(Exception):
    """Raised for problems with the input file (exit code 2)."""


# ---- loading ---------------------------------------------------------------

def _load_sqlite(path):
    uri = path.resolve().as_uri() + "?mode=ro"  # read-only; never creates the file
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM tickets").fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise InputError(f"Cannot read tickets table from {path}: {exc}") from exc
    return [dict(row) for row in rows]


def _load_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise InputError(f"Cannot read JSON from {path}: {exc}") from exc
    if isinstance(data, dict):
        data = data.get("tickets", [data])
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise InputError("JSON must be a ticket object or a list of ticket objects.")
    return data


def _load_csv(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        raise InputError(f"Cannot read CSV from {path}: {exc}") from exc


def load_raw_tickets(path):
    path = Path(path)
    if not path.is_file():
        raise InputError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix in DB_SUFFIXES:
        return _load_sqlite(path), "app"
    if suffix == ".json":
        return _load_json(path), "extended"
    if suffix == ".csv":
        return _load_csv(path), "extended"
    raise InputError(f"Unsupported file type '{suffix}'. Use .db, .json or .csv.")


# ---- normalising -----------------------------------------------------------

def _clean(value):
    """Return a stripped string, or None for missing/placeholder values."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in PLACEHOLDERS else text


def normalise(raw_rows):
    """Map each raw row to canonical fields; row numbers are 1-based."""
    tickets = []
    for position, raw in enumerate(raw_rows, start=1):
        ticket = {"row": position, "id": None, "title": None, "assignee": None,
                  "status": None, "priority": None, "created": None}
        for key, value in raw.items():
            canonical = FIELD_ALIASES.get(re.sub(r"[^a-z0-9]", "", str(key).lower()))
            if canonical and ticket[canonical] is None:
                ticket[canonical] = _clean(value)
        tickets.append(ticket)
    return tickets


def parse_created(text):
    """Parse an ISO-style date or datetime to a date. Returns None if unreadable."""
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


# ---- helpers ---------------------------------------------------------------

def _id_sort_key(value):
    return (0, int(value), "") if value.isdigit() else (1, 0, value)


def _label(ticket, duplicate_ids=()):
    """`ID`, plus the row number when the ID is not unique; 'row N' if there is no ID."""
    if not ticket["id"]:
        return f"row {ticket['row']}"
    if ticket["id"] in duplicate_ids:
        return f"`{ticket['id']}` (row {ticket['row']})"
    return f"`{ticket['id']}`"


def _ticket_sort_key(ticket):
    if ticket["id"]:
        return (0, _id_sort_key(ticket["id"]), ticket["row"])
    return (1, (0, 0, ""), ticket["row"])


def _canonical_hint(value, allowed):
    squeezed = re.sub(r"[^a-z0-9]", "", value.lower())
    for candidate in allowed:
        if re.sub(r"[^a-z0-9]", "", candidate.lower()) == squeezed:
            return candidate
    return None


# ---- checks ----------------------------------------------------------------

def find_duplicates(tickets):
    by_id = {}
    for ticket in tickets:
        if ticket["id"]:
            by_id.setdefault(ticket["id"], []).append(ticket["row"])
    dupes = {tid: rows for tid, rows in by_id.items() if len(rows) > 1}
    return [(tid, dupes[tid]) for tid in sorted(dupes, key=_id_sort_key)]


def find_missing_ids(tickets):
    return [t["row"] for t in tickets if not t["id"]]


def find_orphans(tickets):
    return sorted((t for t in tickets if not t["assignee"]), key=_ticket_sort_key)


def find_invalid(tickets, field, allowed):
    found = []
    for ticket in sorted(tickets, key=_ticket_sort_key):
        value = ticket[field]
        if value not in allowed:
            found.append((ticket, value))
    return found


def count_by(tickets, field, allowed):
    counts = {value: 0 for value in allowed}
    invalid = 0
    for ticket in tickets:
        if ticket[field] in counts:
            counts[ticket[field]] += 1
        else:
            invalid += 1
    return counts, invalid


def find_stale(tickets, as_of, stale_days):
    """Unresolved tickets created more than stale_days before as_of."""
    stale, unreadable = [], []
    for ticket in tickets:
        if ticket["status"] in RESOLVED_STATUSES:
            continue
        created = parse_created(ticket["created"])
        if created is None:
            unreadable.append(ticket)
        elif (as_of - created).days > stale_days:
            stale.append((ticket, (as_of - created).days))
    stale.sort(key=lambda item: (-item[1], _ticket_sort_key(item[0])))
    unreadable.sort(key=_ticket_sort_key)
    return stale, unreadable


# ---- report ----------------------------------------------------------------

def _bullets(lines):
    return lines if lines else ["None"]


def _status_cell(count):
    return "FAIL" if count else "PASS"


def build_report(source_label, raw_rows, profile, as_of, stale_days):
    """Return (report_text, exit_code)."""
    allowed = PROFILES[profile]
    tickets = normalise(raw_rows)

    duplicates = find_duplicates(tickets)
    duplicate_ids = {tid for tid, _ in duplicates}

    def label(ticket):
        return _label(ticket, duplicate_ids)

    missing_ids = find_missing_ids(tickets)
    orphans = find_orphans(tickets)
    bad_status = find_invalid(tickets, "status", allowed["statuses"])
    bad_priority = find_invalid(tickets, "priority", allowed["priorities"])
    status_counts, status_invalid = count_by(tickets, "status", allowed["statuses"])
    priority_counts, priority_invalid = count_by(tickets, "priority", allowed["priorities"])
    stale, unreadable = find_stale(tickets, as_of, stale_days)

    duplicate_count = len(duplicates) + len(missing_ids)
    errors = duplicate_count + len(orphans) + len(bad_status) + len(bad_priority)
    warnings = len(stale) + len(unreadable)

    out = [
        "# Ticket Quality Report",
        f"- Source: {source_label}",
        f"- Profile: {profile} "
        f"(statuses: {', '.join(allowed['statuses'])}; "
        f"priorities: {', '.join(allowed['priorities'])})",
        f"- As of: {as_of.isoformat()} (stale threshold: {stale_days} days)",
        f"- Tickets analysed: {len(tickets)}",
        "",
        "## Summary",
        "| Check | Result | Count | Severity |",
        "|---|---|---|---|",
        f"| Duplicate or missing ticket IDs | {_status_cell(duplicate_count)} | {duplicate_count} | Error |",
        f"| Orphan tickets (no assignee) | {_status_cell(len(orphans))} | {len(orphans)} | Error |",
        f"| Invalid status values | {_status_cell(len(bad_status))} | {len(bad_status)} | Error |",
        f"| Invalid priority values | {_status_cell(len(bad_priority))} | {len(bad_priority)} | Error |",
        f"| Stale tickets (unresolved, older than {stale_days} days) | "
        f"{'WARN' if stale else 'PASS'} | {len(stale)} | Warning |",
        f"| Unreadable created dates (unresolved tickets) | "
        f"{'WARN' if unreadable else 'PASS'} | {len(unreadable)} | Warning |",
        "",
        "## Tickets by status",
        "| Status | Count |",
        "|---|---|",
    ]
    out += [f"| {value} | {count} |" for value, count in status_counts.items()]
    out += [f"| Invalid or missing | {status_invalid} |", f"| **Total** | {len(tickets)} |", "",
            "## Tickets by priority", "| Priority | Count |", "|---|---|"]
    out += [f"| {value} | {count} |" for value, count in priority_counts.items()]
    out += [f"| Invalid or missing | {priority_invalid} |", f"| **Total** | {len(tickets)} |", "",
            "## Findings", "", "### Duplicate or missing ticket IDs"]

    lines = [f"- ID `{tid}` used by rows {', '.join(map(str, rows))}" for tid, rows in duplicates]
    lines += [f"- Row {row} has no ticket ID" for row in missing_ids]
    out += _bullets(lines)

    out += ["", "### Orphan tickets (no assignee)"]
    out += _bullets([f"- {label(t)}" for t in orphans])

    for heading, items, allowed_values in (
        ("Invalid status values", bad_status, allowed["statuses"]),
        ("Invalid priority values", bad_priority, allowed["priorities"]),
    ):
        out += ["", f"### {heading}"]
        lines = []
        for ticket, value in items:
            shown = f'"{value}"' if value else "(missing)"
            hint = _canonical_hint(value, allowed_values) if value else None
            suffix = f' (did you mean "{hint}"?)' if hint else ""
            lines.append(f"- {label(ticket)}: found {shown}{suffix}")
        out += _bullets(lines)

    out += ["", f"### Stale tickets (unresolved, older than {stale_days} days)"]
    out += _bullets([
        f"- {label(t)}: {t['title'] or '(no title)'} | status {t['status'] or '(missing)'} | {age} days old"
        for t, age in stale
    ])

    out += ["", "### Unreadable created dates (unresolved tickets)"]
    out += _bullets([f"- {label(t)}: found {t['created'] or '(missing)'!r}" for t in unreadable])

    if errors:
        result, code = "FAIL", 1
    elif warnings:
        result, code = "PASS WITH WARNINGS", 1
    else:
        result, code = "PASS", 0
    out += ["", f"**Result: {result}** ({errors} errors, {warnings} warnings)",
            "Read-only: no files were modified.", ""]
    return "\n".join(out), code


# ---- command line ----------------------------------------------------------

def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Read-only ticket data-quality report.")
    parser.add_argument("path", nargs="?", default="data/tickets.db",
                        help="ticket file: .db, .json or .csv (default: data/tickets.db)")
    parser.add_argument("--as-of", dest="as_of", default=None,
                        help="reference date YYYY-MM-DD (default: today)")
    parser.add_argument("--stale-days", type=int, default=30,
                        help="age in days above which an unresolved ticket is stale")
    parser.add_argument("--profile", choices=sorted(PROFILES), default=None,
                        help="allowed values: 'app' (default for .db) or 'extended' (default otherwise)")
    return parser.parse_args(argv)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parse_args(argv)
    try:
        if args.as_of:
            try:
                as_of = date.fromisoformat(args.as_of)
            except ValueError as exc:
                raise InputError(f"--as-of must be YYYY-MM-DD, got '{args.as_of}'") from exc
        else:
            as_of = date.today()
        if args.stale_days < 0:
            raise InputError("--stale-days must be 0 or more")
        raw_rows, default_profile = load_raw_tickets(args.path)
        report, code = build_report(args.path, raw_rows, args.profile or default_profile,
                                    as_of, args.stale_days)
    except InputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
