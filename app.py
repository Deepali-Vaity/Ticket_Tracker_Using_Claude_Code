"""IT Helpdesk Ticket Tracker - Flask application (routes only)."""

import os

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import models
from database import init_db

TITLE_MAX = 100
DESCRIPTION_MAX = 2000
ENGINEER_MAX = 100

app = Flask(__name__)
# Set SECRET_KEY in the environment for any real deployment.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")

init_db()


@app.context_processor
def inject_constants():
    """Make the allowed values and badge colours available in all templates."""
    return {
        "PRIORITIES": models.PRIORITIES,
        "STATUSES": models.STATUSES,
        "STATUS_COLORS": {"Open": "primary", "In Progress": "warning", "Closed": "success"},
        "PRIORITY_COLORS": {"Low": "secondary", "Medium": "info", "High": "danger"},
        "UNASSIGNED": models.UNASSIGNED,
        "ENGINEER_MAX": ENGINEER_MAX,
    }


@app.route("/")
def index():
    """List tickets, filtered with ?status=..., ?priority=... and/or ?engineer=..."""
    status = request.args.get("status", "")
    if status not in models.STATUSES:
        status = ""
    priority = request.args.get("priority", "")
    if priority not in models.PRIORITIES:
        priority = ""
    engineer = request.args.get("engineer", "").strip()
    tickets = models.list_tickets(status or None, engineer or None, priority or None)
    return render_template(
        "index.html",
        tickets=tickets,
        current_status=status,
        current_priority=priority,
        current_engineer=engineer,
        engineers=models.list_engineers(),
    )


@app.route("/tickets/new", methods=["GET", "POST"])
def create_ticket():
    """Show the form (GET) or validate and save a new ticket (POST)."""
    form = {"title": "", "description": "", "priority": "Medium", "assigned_engineer": ""}
    if request.method == "POST":
        form["title"] = request.form.get("title", "").strip()
        form["description"] = request.form.get("description", "").strip()
        form["priority"] = request.form.get("priority", "")
        form["assigned_engineer"] = request.form.get("assigned_engineer", "").strip()

        errors = []
        if not form["title"]:
            errors.append("Title is required.")
        elif len(form["title"]) > TITLE_MAX:
            errors.append(f"Title must be at most {TITLE_MAX} characters.")
        if not form["description"]:
            errors.append("Description is required.")
        elif len(form["description"]) > DESCRIPTION_MAX:
            errors.append(f"Description must be at most {DESCRIPTION_MAX} characters.")
        if form["priority"] not in models.PRIORITIES:
            errors.append("Please choose a valid priority.")
        if len(form["assigned_engineer"]) > ENGINEER_MAX:
            errors.append(f"Engineer name must be at most {ENGINEER_MAX} characters.")

        if errors:
            for message in errors:
                flash(message, "danger")
        else:
            ticket_id = models.create_ticket(
                form["title"], form["description"], form["priority"],
                form["assigned_engineer"] or None,
            )
            flash(f"Ticket #{ticket_id} created.", "success")
            return redirect(url_for("ticket_detail", ticket_id=ticket_id))

    return render_template(
        "create_ticket.html", form=form, title_max=TITLE_MAX, description_max=DESCRIPTION_MAX
    )


@app.route("/tickets/<int:ticket_id>")
def ticket_detail(ticket_id):
    ticket = models.get_ticket(ticket_id)
    if ticket is None:
        abort(404)
    return render_template("ticket_detail.html", ticket=ticket)


@app.route("/tickets/<int:ticket_id>/status", methods=["POST"])
def update_ticket_status(ticket_id):
    if models.get_ticket(ticket_id) is None:
        abort(404)
    new_status = request.form.get("status", "")
    if models.update_status(ticket_id, new_status):
        flash(f"Status updated to '{new_status}'.", "success")
    else:
        flash("Invalid status.", "danger")
    return redirect(url_for("ticket_detail", ticket_id=ticket_id))


@app.route("/tickets/<int:ticket_id>/engineer", methods=["POST"])
def update_ticket_engineer(ticket_id):
    """Assign an engineer; an empty name clears the assignment."""
    if models.get_ticket(ticket_id) is None:
        abort(404)
    engineer = request.form.get("assigned_engineer", "").strip()
    if len(engineer) > ENGINEER_MAX:
        flash(f"Engineer name must be at most {ENGINEER_MAX} characters.", "danger")
    elif models.update_engineer(ticket_id, engineer or None):
        flash(f"Assigned to {engineer}." if engineer else "Ticket unassigned.", "success")
    return redirect(url_for("ticket_detail", ticket_id=ticket_id))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", counts=models.get_dashboard_counts())


@app.errorhandler(404)
def not_found(_error):
    return render_template("base.html", not_found=True), 404


if __name__ == "__main__":
    # debug=True is for local development only.
    app.run(debug=True)
