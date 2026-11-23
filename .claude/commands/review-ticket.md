---
description: Review a ticket file for valid status, priority, required fields and naming consistency (read-only)
argument-hint: <ticket-file>
allowed-tools: Read, Grep, Glob
---

# /review-ticket

Review the ticket file at: `$ARGUMENTS`

You are a **read-only reviewer**. You must **never** create, edit, move, delete or
overwrite any file, and never run shell commands. Your only job is to read the
file and report findings. Do not offer to apply fixes automatically; describe them.

## 0. Input handling

- If `$ARGUMENTS` is empty, stop and print **only** the usage block at the bottom (no
  report header, no "No files were modified." line). Do not guess a file.
- Read the file. You may use Glob or Grep only to locate the path the user gave. If it does not exist or cannot be read, report that and stop.
- Supported formats:
  - **JSON**: one ticket object, or a list of ticket objects.
  - **CSV**: a header row, one ticket per row.
  - **Plain text / Markdown**: `Key: Value` lines (optionally inside `---` front matter).
    Several tickets may be separated by `---` or a blank-line-delimited heading.
- Any other format (for example a SQLite `.db` file): say it is not supported and stop.
- A file with no recognisable tickets: report that as an Error and stop.

## 1. Reference rules

**Allowed statuses**, in lifecycle order: `Open` -> `In Progress` -> `Resolved` -> `Closed`

**Allowed priorities:** `Low`, `Medium`, `High`, `Critical`

**Required fields** (field names are matched flexibly, ignoring case, spaces, `_` and `-`):

| Required field | Accepted names (examples) |
|---|---|
| Ticket ID | `id`, `ticket_id`, `ticket id`, `key` |
| Title | `title`, `summary`, `subject` |
| Assignee | `assignee`, `assigned_to`, `assigned engineer`, `assigned_engineer`, `owner` |
| Status | `status`, `state` |
| Priority | `priority` |

A required field is **missing** if it is absent, empty, whitespace-only, or a placeholder
such as `null`, `none`, `n/a`, `tbd`.

## 2. Checks to perform on every ticket

1. **Required fields.** Identify every missing field. Name the ticket (by ID, or by
   position such as "row 3" if the ID itself is missing).
2. **Status value.** The value must be one of the allowed statuses.
   - Exact match: fine.
   - Matches only after ignoring case, spaces, `_`, `-` (for example `in_progress`, `CLOSED`):
     **Warning** (non-canonical spelling; give the canonical value).
   - Anything else (for example `Done`, `Reopened`): **Error**.
3. **Priority value.** Same rules against the allowed priorities. An unrecognised value
   such as `Urgent` or `P1` is an **Error**; a case/spelling variant is a **Warning**.
4. **Status transitions.** Look for a history: a field named like `history`,
   `status_history`, `transitions`, or text such as `Open -> In Progress`.
   - Only forward, one step at a time is valid:
     `Open -> In Progress`, `In Progress -> Resolved`, `Resolved -> Closed`.
   - Skipping a step (for example `Open -> Resolved`) or moving backwards
     (for example `Closed -> Open`) is an **Error**.
   - A repeated status (`Open -> Open`) is a **Warning**.
   - Also check that the ticket's current status equals the last status in its history;
     a mismatch is an **Error**.
   - A move back to an earlier status is an Error even if the ticket was legitimately
     reopened; the lifecycle above has no reopen step. Mention this in a Recommendation.
   - If a ticket has **no history**, you cannot verify transitions. Report a single
     **Warning** for the whole file: "Transitions not verifiable (no status history)",
     listing every affected ticket ID. Do not invent a violation.
5. **Naming and formatting consistency** (across the whole file, not only one ticket):
   - Ticket ID pattern (for example `TCK-001` mixed with `1` or `tck_2`), duplicate IDs.
     Report a duplicate ID once, as an Error listing every position that uses it
     ("row N" = 1-based position of the ticket in the file, JSON array order included).
   - Field-name variants for the same thing (`assignee` in one ticket, `assigned_to` in another).
   - Mixed case or spelling of status and priority values.
   - Mixed date formats (`2026-11-21` vs `21/11/2026`), leading or trailing whitespace,
     empty strings where a field exists, and titles starting with a lowercase letter when
     the other titles start with a capital.
   - Unknown extra fields that look like typos of known fields (for example `assigne`).

Be precise. Quote the offending value. Do not report the same root cause more than once
per ticket (for example an invalid status that also differs from the history is one
finding, mention both facts); if many tickets share one problem, report it once and list
the affected IDs. Recommendations may group related findings, so their count need not
match the number of Errors and Warnings.

## 3. Severity

- **Errors**: missing required fields, invalid status or priority values, invalid
  transitions, status/history mismatch, unreadable or empty input, duplicate IDs.
- **Warnings**: non-canonical spellings, naming or formatting inconsistencies,
  transitions that could not be verified, suspicious extra fields.
- **Recommendations**: concrete, suggested fixes and improvements. Suggestions only.

## 4. Output format

Use exactly this structure:

```
Ticket review: <file path>
Tickets reviewed: <n> | Errors: <n> | Warnings: <n> | Recommendations: <n>

## Errors
- [<ticket id>] <field>: <what is wrong> (found "<value>")
  (or "None")

## Warnings
- [<ticket id>] <field>: <what is inconsistent or unverifiable>
  (or "None")

## Recommendations
- <actionable suggestion, with the canonical value or format to use>
  (or "None")

Result: PASS | PASS WITH WARNINGS | FAIL
No files were modified.
```

In an empty section print the single word `None`. `FAIL` if there is at least one Error; `PASS WITH WARNINGS` if there are only Warnings;
otherwise `PASS`. Always end with the line `No files were modified.`

## Example usage

```
/review-ticket tickets/sample-tickets.json
/review-ticket exports/helpdesk-2026-11.csv
/review-ticket docs/TCK-104.md
```

Usage when no file is given:

```
Usage: /review-ticket <ticket-file>
Supported: .json, .csv, .md/.txt (Key: Value). This command only reads; it never edits files.
```
