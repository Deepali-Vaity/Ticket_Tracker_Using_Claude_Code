# IT Helpdesk Ticket Tracker

A beginner-friendly web app to log and track IT support tickets.
Built with Python 3.12, Flask, SQLite and Bootstrap 5.

## Features
- Create tickets (title, description, priority)
- List all tickets and filter by status
- View ticket details
- Update ticket status (Open, In Progress, Closed)
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
| `/` | Ticket list; `?status=Open` (or `In Progress`, `Closed`) filters |
| `/tickets/new` | Create a ticket |
| `/tickets/<id>` | Ticket details and status update |
| `/dashboard` | Counts summary |

## Configuration
- `SECRET_KEY`: set this environment variable for any non-local use.
- `TICKET_DB_PATH`: optional path to use a different database file.

## Notes
- No authentication; intended as a learning project.
- `debug=True` in `app.py` is for local development only.
