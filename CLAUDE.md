# CLAUDE.md

Guidance for Claude (and any developer) working on the **IT Helpdesk Ticket Tracker**.

## Working Agreement for Claude Sessions (read first)

These rules apply to every change, however small it looks.

1. **Plan first.** Always produce an implementation plan before touching code.
2. **Never edit code immediately.** Reading, searching and running the app are fine; editing is not until the plan is approved.
3. **Wait for approval.** Do not proceed on silence or on a vague "ok". Ask if unsure.
4. **Keep changes minimal.** Do only what was approved. No drive-by refactors, renames, reformatting or new dependencies.
5. **Explain impacted files before editing.** List each file, what changes in it and why, plus anything that could be affected indirectly (templates, routes, DB schema).
6. **Suggest a git checkpoint before major modifications** (schema changes, multi-file changes, dependency changes, deletions). See [Git Workflow](#5-git-workflow).
7. **Verify after changes.** Run the app and exercise the affected behaviour. Report failures honestly, with output.
8. **Summarize when completed.** List files changed, behaviour changed, how it was verified, and anything left undone.

If a request conflicts with these rules, state the conflict and ask.

---

## 1. Project Overview

A beginner-friendly web app for logging and tracking IT support tickets.

| Item | Value |
|---|---|
| Stack | Python 3.12, Flask (3.x), SQLite (`sqlite3`, no ORM), Jinja2, Bootstrap 5.3 (CDN) |
| Audience | Learners; readability beats cleverness |
| Auth | None (single-user learning project) |

**Features:** create ticket, list tickets, view details, update status, filter by status, dashboard counts.

**Ticket fields:** `id`, `title`, `description`, `priority` (Low/Medium/High), `status` (Open/In Progress/Closed), `created_at`.

**Out of scope unless explicitly requested:** authentication, editing or deleting tickets, pagination, user accounts, REST API, ORMs, JS frameworks.

**Commands** (run from the `ticket-tracker/` folder, Windows PowerShell):

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python database.py --seed     # optional: 8 sample tickets (no-op if data exists)
python app.py                 # http://127.0.0.1:5000
```

Environment variables: `SECRET_KEY` (session signing), `TICKET_DB_PATH` (alternate DB file, e.g. for tests).

## 2. Architecture

```
Browser (Bootstrap 5 pages)
   -> app.py        routes, validation, flash messages   (no SQL)
   -> models.py     all SQL + PRIORITIES / STATUSES      (no Flask)
   -> database.py   connection, schema, seed data
   -> data/tickets.db   (created at runtime, not committed)
```

| File | Responsibility |
|---|---|
| `app.py` | Flask app, routes, input validation, context processor (badge colours, allowed values), 404 handler |
| `models.py` | Ticket CRUD-style functions, dashboard counts, the single source of truth for allowed values |
| `database.py` | `get_connection()`, `init_db()`, `seed_sample_data()`, `SAMPLE_TICKETS` |
| `templates/` | `base.html` layout; `index`, `create_ticket`, `ticket_detail`, `dashboard` extend it |
| `static/styles.css` | Small custom styles only |

**Routes**

| Method | URL | Purpose |
|---|---|---|
| GET | `/` | List; `?status=` filters (invalid values are ignored); `?engineer=<name>` or `?engineer=__unassigned__` filters by engineer; `?priority=Low|Medium|High` filters by priority (invalid ignored); all three combine |
| GET/POST | `/tickets/new` | Create ticket |
| GET | `/tickets/<int:id>` | Detail (404 if missing) |
| POST | `/tickets/<int:id>/status` | Update status, then redirect to detail |
| POST | `/tickets/<int:id>/engineer` | Assign engineer (empty = unassign), then redirect to detail |
| GET | `/dashboard` | Counts by status and priority |

**Claude tooling (read-only, outside the app):** `.claude/commands/review-ticket.md` (`/review-ticket <file>`) reviews one ticket file; `.claude/skills/ticket-quality/` (script `scripts/ticket_quality.py`, tested in `tests/test_ticket_quality.py`) produces a backlog quality report from `data/tickets.db` or a JSON/CSV file. Neither modifies data.

**Layer rules:** `app.py` never contains SQL; `models.py` never imports Flask; templates contain presentation only (no business logic beyond simple conditionals/loops).

## 3. Coding Standards

- Follow PEP 8; 4-space indent; lines around 100 characters max.
- Use clear, descriptive names; `snake_case` for functions/variables, `UPPER_CASE` for constants.
- Every module and public function gets a short docstring explaining *why*/*what*, not restating the code.
- Prefer the standard library. Add a dependency only with explicit approval and pin it in `requirements.txt`.
- Keep functions small and single-purpose; avoid clever one-liners a beginner could not read.
- Comments explain non-obvious reasoning only.
- Templates: extend `base.html`, use `url_for()` for every link/asset, let Jinja autoescape (never use `|safe` on user data).
- Do not leave dead code, debug prints or commented-out blocks.
- Allowed priority/status values are defined **once** in `models.py`. Templates receive them through the context processor; do not hard-code them elsewhere.

## 4. Design Principles

- **Simplicity first:** the simplest thing that works and is easy to explain to a beginner.
- **Separation of concerns:** routes, data access and presentation stay in their own layers.
- **Single source of truth:** constants, schema rules and colour maps are defined in one place.
- **Server-side validation is authoritative;** HTML attributes (`required`, `maxlength`) are only conveniences.
- **Post/Redirect/Get:** every successful POST redirects; never render a page directly from a successful POST.
- **Minimal UI:** Bootstrap components first; custom CSS only when Bootstrap cannot do it.
- **Accessibility basics:** labels tied to inputs, `aria-label` on icon-only/unlabelled controls, sufficient contrast via Bootstrap badges.
- **Backwards compatibility:** do not change URLs, field names or schema without a plan covering existing data.

## 5. Git Workflow

> At the time of writing the project folder is **not yet a git repository**. Before the first modification session, suggest `git init` and an initial commit (only after the user agrees).

- `main` is always runnable. Work on short-lived branches: `feature/<topic>`, `fix/<topic>`, `chore/<topic>`.
- **Checkpoint before major modifications:** suggest a commit (or tag) first, e.g. `git add -A && git commit -m "checkpoint: before <change>"`. "Major" means schema changes, changes touching 3+ files, dependency changes, deletions or renames, and large template rewrites.
- Commit only when the user asks. Never force-push or rewrite history unprompted.
- Commit messages: imperative, <= 72 chars subject, body explains *why*. One logical change per commit.
- `.gitignore` must contain: `.venv/`, `__pycache__/`, `*.pyc`, `data/*.db`, `.env`.
- Never commit secrets, `.env` files or the SQLite database.

## 6. Testing Strategy

Current state: 65 `pytest` tests in `tests/` (`test_models.py`, `test_routes.py`). Run with `pip install -r requirements-dev.txt` then `python -m pytest -v`. Run them after every change and add or update tests for any behaviour you change.

`tests/conftest.py` sets `TICKET_DB_PATH` to a temp file **before** importing the app (database.py reads it at import time) and empties the table before each test. Never bypass this; tests must not touch the real `data/tickets.db`.

Coverage includes:
- Create: valid input, empty title/description, invalid priority, over-length input.
- List and filter: all, each status, invalid status value (falls back to all).
- Detail: existing ticket and unknown ID (404).
- Status update: each valid status, invalid status, unknown ticket (404).
- Dashboard: counts correct, including an empty database.
- Models: parameterised queries behave correctly with quotes/special characters.

**Manual verification checklist after any change** (see also Change Management):
1. App starts without errors.
2. Affected pages return 200 (or the intended redirect / 404).
3. Create -> appears in list -> detail opens -> status change persists -> filter and dashboard counts reflect it.
4. Invalid input shows an error and does not write to the DB.
5. Use a throwaway DB (`$env:TICKET_DB_PATH = "$env:TEMP\test.db"`) for destructive checks.

Report what was and was not verified. Never claim success without having run something.

## 7. Database Rules

- SQLite via the standard `sqlite3` module. File: `data/tickets.db`, created automatically; never committed.
- Schema (single table `tickets`):

| Column | Type | Rules |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `title` | TEXT | NOT NULL |
| `description` | TEXT | NOT NULL |
| `priority` | TEXT | NOT NULL, CHECK in (Low, Medium, High) |
| `status` | TEXT | NOT NULL, DEFAULT 'Open', CHECK in (Open, In Progress, Closed) |
| `created_at` | TEXT | NOT NULL, `YYYY-MM-DD HH:MM:SS` local time, set by the app |
| `assigned_engineer` | TEXT | NULL = unassigned; free text, max 100 chars, trimmed; matched case-insensitively. Added by a migration in `init_db()` for older databases |

- **All SQL lives in `models.py`** (plus schema/seed in `database.py`).
- **Always parameterise** with `?` placeholders. Never build SQL from user input. The only f-string SQL allowed is `_count_by`, which uses hard-coded column names, never request data.
- Open a connection per operation; close it in `finally`; use `with conn:` for transactions (commit/rollback).
- Schema changes require an approved plan that covers: migration of existing rows, updating `SCHEMA`, `models.py`, templates and the seed data, and a backup/checkpoint first. `CREATE TABLE IF NOT EXISTS` does **not** alter existing tables.
- Seed data only loads into an empty table. Never seed or reset the real database without explicit approval.
- Never delete or overwrite `data/tickets.db` without asking.

## 8. Change Management Process

For every change request:

1. **Understand:** read the relevant code; restate the request. Ask questions if ambiguous.
2. **Plan:** present an implementation plan: approach, alternatives if relevant, risks.
3. **Impact list:** name every file to be changed, what changes, and indirect effects (routes, templates, schema, README/CLAUDE.md).
4. **Approval gate:** stop and wait. No edits until the user approves.
5. **Checkpoint:** for major changes, suggest a git commit/tag (or a copy of the folder if git is not set up).
6. **Implement minimally:** only what was approved. If something extra is needed, stop and ask.
7. **Verify:** run the app, run tests if present, walk the manual checklist (section 6).
8. **Summarize:** files changed, behaviour before/after, verification done, known gaps, follow-ups.
9. **Docs:** update `README.md` / `CLAUDE.md` only when behaviour, commands or conventions changed, and say so in the summary.

Small fixes (typos, one-line bugs) still follow steps 2-4, but the plan can be one or two sentences.

## 9. Error Handling Guidelines

- Validate all user input in `app.py` before calling `models`; collect all errors and show them with `flash(message, "danger")`.
- On validation failure, re-render the form with the user's input preserved (HTTP 200); do not write to the DB.
- Unknown ticket IDs: `abort(404)`; the 404 handler renders a friendly page.
- Invalid `?status=` filter: ignore it and show all tickets (do not error).
- Database errors: let `with conn:` roll back; always close connections in `finally`. Do not swallow exceptions silently. If handling `sqlite3.Error` is added, log it and show a generic message.
- Never show stack traces, SQL or file paths to users. `debug=True` is for local development only; production must run with debug off.
- User-facing messages are short, plain English, and say how to fix the problem.
- Do not use bare `except:`; catch specific exceptions.

## 10. Security Guidelines

- **SQL injection:** parameterised queries only (section 7).
- **XSS:** rely on Jinja autoescaping; never mark user content `|safe`; never build HTML with string concatenation.
- **CSRF:** the app currently has no CSRF protection on its POST forms. If the app is ever deployed beyond local use, add it (for example Flask-WTF) via an approved plan.
- **Secrets:** `SECRET_KEY` must come from the environment outside local dev; the built-in default is for development only. Never hard-code or commit real secrets, and never echo credentials users paste into chat.
- **Debug mode:** never run `debug=True` on a shared or public host.
- **Input limits:** title <= 100 and description <= 2000 characters, enforced server-side.
- **Dependencies:** minimal and pinned; review any addition; keep Flask updated for security fixes.
- **Data:** ticket text may contain personal or client information. Do not log full ticket contents; if real or regulated data (GDPR etc.) will be stored, consult the Data Privacy Officer before go-live.
- **CDN assets:** Bootstrap is loaded from jsDelivr with a pinned version. If stricter security is needed, add SRI hashes or self-host.
- **No authentication exists:** anyone who can reach the app can read and change tickets. Do not expose it to a network without adding access control.
