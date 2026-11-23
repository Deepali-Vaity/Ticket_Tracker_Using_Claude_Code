# IT Helpdesk Ticket Tracker

A beginner-friendly web app to log and track IT support tickets.
Built with Python 3.12, Flask, SQLite and Bootstrap 5.

## Features
- Create tickets (title, description, priority)
- List all tickets and filter by status
- View ticket details
- Update ticket status (Open, In Progress, Closed)
- Assign an engineer to a ticket and filter tickets by engineer (or "Unassigned")
- Dashboard with ticket counts by status and priority

## Run locally (Windows PowerShell)

```powershell
cd ticket-tracker
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python database.py --seed    # optional: load 8 sample tickets
python app.py
```

Open http://127.0.0.1:5000 in your browser.

If PowerShell blocks activation, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

macOS/Linux: use `python3.12 -m venv .venv` and `source .venv/bin/activate`.

## Run tests

```powershell
pip install -r requirements-dev.txt
python -m pytest -v
```

Tests use a temporary database, so `data/tickets.db` is never touched.

## Protecting `data/` from Claude Code (optional hook)

A Claude Code `PreToolUse` hook stops Claude's `Edit`, `MultiEdit`, `Write` and
`NotebookEdit` tools from changing anything under `data/` (except `data/processed/`).
Reading is not affected. A blocked write exits with code 2 and shows:

> Raw data files are protected.
>
> Write changes only to data/processed.

**Installation**
1. Keep both files in place: `.claude/hooks/protect-data.py` and `.claude/settings.json`
   (the settings file registers the hook; no other setup is needed).
2. Make sure `python` works in a terminal (`python --version`). The hook runs through it.
3. Restart Claude Code in this folder and accept the project hook if prompted.
4. Run `/hooks` and confirm a `PreToolUse` entry for `Edit|MultiEdit|Write|NotebookEdit`.
5. Test it: ask Claude to create `data/test.txt`. It should be refused with the message above.

**Limits:** only Claude's edit tools are intercepted. Shell commands run through Bash
(for example `rm data/tickets.db`) and the Flask app itself can still change `data/`.
If `python` cannot be found when the hook runs, Claude Code treats it as a non-blocking
error and the write is allowed, so always do the test in step 5.

## Project layout

| File | Purpose |
|---|---|
| `app.py` | Flask routes, validation, flash messages |
| `database.py` | SQLite connection, schema, sample data |
| `models.py` | All ticket queries |
| `templates/` | Jinja2 pages (Bootstrap 5 via CDN) |
| `static/styles.css` | Small custom styles |
| `data/tickets.db` | SQLite file, created automatically |

## Routes

| URL | Description |
|---|---|
| `/` | Ticket list; `?status=Open` (or `In Progress`, `Closed`) and `?engineer=Name` and `?priority=Low` (or `Medium`, `High`) filters, all combinable |
| `/tickets/<id>/engineer` | POST: assign or clear the engineer (used by the detail page) |
| `/tickets/new` | Create a ticket |
| `/tickets/<id>` | Ticket details and status update |
| `/dashboard` | Counts summary |

## Configuration
- `SECRET_KEY`: set this environment variable for any non-local use.
- `TICKET_DB_PATH`: optional path to use a different database file.

## Notes
- No authentication; intended as a learning project.
- `debug=True` in `app.py` is for local development only.
