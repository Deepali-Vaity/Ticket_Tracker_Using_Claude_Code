---
name: ticket-quality
description: Evaluate ticket data quality and backlog health. Use when the user asks to check ticket quality, validate tickets, review the support backlog, analyze ticket data, or find duplicate, orphan (unassigned), stale, or invalid-status/priority tickets, or wants ticket counts by status or priority. Runs a read-only script and reports a deterministic summary table.
allowed-tools: Read, Bash(python .claude/skills/ticket-quality/scripts/ticket_quality.py:*)
---

# ticket-quality

Evaluates a ticket data set and produces a fixed-format quality report. All counting,
date maths and validation is done by the bundled script, **not by you**, so the same input
always gives the same report. Your job is to run it, present its output, and explain it.

## When to use (trigger examples)

- "Check ticket quality"
- "Validate the tickets" / "validate tickets.json"
- "Review the support backlog"
- "Analyze the ticket data"
- "Are there duplicate or unassigned tickets?"
- "How many tickets are stale?" / "Show tickets by status and priority"

Do **not** use for editing, fixing or deleting tickets, or for a field-by-field review of a
single ticket file (that is `/review-ticket`).

## Inputs

| Input | Default | Notes |
|---|---|---|
| Ticket source | `data/tickets.db` | `.db`/`.sqlite` (SQLite `tickets` table), `.json` or `.csv`. If the user names a file, use it. |
| As-of date | today | `--as-of YYYY-MM-DD`. Pass it when the user gives a date, and say which date was used. |
| Stale threshold | 30 days | `--stale-days N` only if the user asks for another value. |
| Profile | `.db` -> `app`; `.json`/`.csv` -> `extended` | `--profile app\|extended` only if the user asks. |

Reference values:

| Profile | Allowed statuses | Allowed priorities |
|---|---|---|
| `app` | Open, In Progress, Closed | Low, Medium, High |
| `extended` | Open, In Progress, Resolved, Closed | Low, Medium, High, Critical |

## Execution steps

1. **Pick the source.** Use the file the user named. If none was named, use `data/tickets.db`.
   Do not search the disk for other files. If the file may not exist, run the script anyway; it
   reports a clear error.
2. **Run the script** from the project root (the folder that contains `data/`), exactly:

   ```
   python .claude/skills/ticket-quality/scripts/ticket_quality.py [PATH] [--as-of YYYY-MM-DD] [--stale-days N] [--profile app|extended]
   ```

3. **Handle the exit code.**
   - `0` = no findings. `1` = findings reported (the report is still valid output).
   - `2` = input error (message on stderr). Tell the user what failed and how to fix it. Do not
     retry with a different file unless the user asks.
4. **Present the report verbatim** in a markdown block or as-is. Never recalculate, round,
   re-sort, merge or drop any number, row or finding.
5. **Add a short interpretation (max 5 bullets)** after the report: what matters most,
   which findings are Errors vs Warnings, and a concrete next step. Use only facts that appear in
   the report. If the report says Result PASS, say so plainly.
6. **Never modify anything.** Do not edit, write, delete or "fix" tickets or files, and do not
   run any other command. Offer fixes as suggestions only.

## The 8 checks (all performed by the script)

1. Duplicate ticket IDs (also reports rows with no ID).
2. Orphan tickets: assignee missing, blank or a placeholder (`null`, `none`, `n/a`, `tbd`).
3. Invalid status values (not in the profile's list; a missing value counts as invalid).
4. Invalid priority values (same rule).
5. Count of tickets by status.
6. Count of tickets by priority.
7. Stale tickets: **unresolved** (status not Resolved/Closed) and created **more than** 30 days
   before the as-of date. Exactly 30 days is not stale. Tickets whose created date cannot be
   read are listed separately as warnings.
8. Summary report table.

## Expected output format

```
# Ticket Quality Report
- Source: <path as given>
- Profile: <app|extended> (statuses: ...; priorities: ...)
- As of: <YYYY-MM-DD> (stale threshold: <n> days)
- Tickets analysed: <n>

## Summary
| Check | Result | Count | Severity |
|---|---|---|---|
| Duplicate or missing ticket IDs | PASS/FAIL | n | Error |
| Orphan tickets (no assignee) | PASS/FAIL | n | Error |
| Invalid status values | PASS/FAIL | n | Error |
| Invalid priority values | PASS/FAIL | n | Error |
| Stale tickets (unresolved, older than <n> days) | PASS/WARN | n | Warning |
| Unreadable created dates (unresolved tickets) | PASS/WARN | n | Warning |

## Tickets by status        (one row per allowed status, then "Invalid or missing" and **Total**)
## Tickets by priority      (same layout)
## Findings                 (one list per check; "None" when empty)

**Result: PASS | PASS WITH WARNINGS | FAIL** (<n> errors, <n> warnings)
Read-only: no files were modified.
```

Severity rule: any Error finding -> `FAIL`; only Warnings -> `PASS WITH WARNINGS`; none -> `PASS`.
Tickets are ordered by ID (numeric IDs first, in numeric order, then text IDs alphabetically);
stale tickets are ordered oldest first.

## Determinism rules

- All numbers come from the script. Never estimate or "double-check" them by hand.
- For repeatable results across days, pass `--as-of`; otherwise "today" is used and the report
  states the date.
- The report shows IDs, titles and statuses only. Never print ticket descriptions or other
  free-text content: tickets may contain personal or client data.

## Example usage

```
Check ticket quality
Validate tickets in exports/helpdesk-2026-11.csv
Review the support backlog as of 2026-12-31
Analyze data/tickets.db and list stale tickets older than 14 days
```
