"""Tests for the Flask routes (app.py)."""

import models

VALID = {"title": "VPN down", "description": "Cannot connect", "priority": "High"}


# ---- list and filter ------------------------------------------------------

def test_index_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"No tickets found" in response.data


def test_index_lists_tickets(client, make_ticket):
    make_ticket(title="Alpha ticket")
    response = client.get("/")
    assert response.status_code == 200
    assert b"Alpha ticket" in response.data


def test_index_filter_by_status(client, make_ticket):
    make_ticket(title="OpenOne")
    make_ticket(title="ClosedOne", status="Closed")
    data = client.get("/?status=Closed").data
    assert b"ClosedOne" in data
    assert b"OpenOne" not in data


def test_index_invalid_status_shows_all(client, make_ticket):
    make_ticket(title="OpenOne")
    make_ticket(title="ClosedOne", status="Closed")
    data = client.get("/?status=bogus").data
    assert b"OpenOne" in data and b"ClosedOne" in data


# ---- create ---------------------------------------------------------------

def test_create_form_loads(client):
    assert client.get("/tickets/new").status_code == 200


def test_create_valid_redirects_to_detail(client):
    response = client.post("/tickets/new", data=VALID)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/tickets/1")
    assert models.get_ticket(1)["title"] == "VPN down"


def test_create_trims_whitespace(client):
    client.post("/tickets/new", data={**VALID, "title": "  padded  "})
    assert models.get_ticket(1)["title"] == "padded"


def test_create_empty_fields_rejected(client):
    response = client.post("/tickets/new", data={**VALID, "title": "", "description": "  "})
    assert response.status_code == 200
    assert b"Title is required" in response.data
    assert b"Description is required" in response.data
    assert models.list_tickets() == []


def test_create_invalid_priority_rejected(client):
    response = client.post("/tickets/new", data={**VALID, "priority": "Urgent"})
    assert b"valid priority" in response.data
    assert models.list_tickets() == []


def test_create_too_long_rejected(client):
    long_title = "x" * 101
    response = client.post("/tickets/new", data={**VALID, "title": long_title})
    assert b"at most 100" in response.data
    assert models.list_tickets() == []


def test_create_failure_keeps_user_input(client):
    response = client.post("/tickets/new", data={**VALID, "description": ""})
    assert b"VPN down" in response.data


# ---- detail ---------------------------------------------------------------

def test_detail_existing(client, make_ticket):
    ticket_id = make_ticket(title="Detail me")
    response = client.get(f"/tickets/{ticket_id}")
    assert response.status_code == 200
    assert b"Detail me" in response.data


def test_detail_unknown_is_404(client):
    assert client.get("/tickets/999").status_code == 404


# ---- status update --------------------------------------------------------

def test_status_update_valid(client, make_ticket):
    ticket_id = make_ticket()
    response = client.post(f"/tickets/{ticket_id}/status", data={"status": "Closed"})
    assert response.status_code == 302
    assert models.get_ticket(ticket_id)["status"] == "Closed"


def test_status_update_invalid(client, make_ticket):
    ticket_id = make_ticket()
    response = client.post(
        f"/tickets/{ticket_id}/status", data={"status": "bogus"}, follow_redirects=True
    )
    assert b"Invalid status" in response.data
    assert models.get_ticket(ticket_id)["status"] == "Open"


def test_status_update_unknown_ticket_is_404(client):
    assert client.post("/tickets/999/status", data={"status": "Closed"}).status_code == 404


# ---- dashboard ------------------------------------------------------------

def test_dashboard_empty(client):
    assert client.get("/dashboard").status_code == 200


def test_dashboard_shows_counts(client, make_ticket):
    make_ticket()
    make_ticket(status="Closed")
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b">2<" in response.data  # total tickets


# ---- security -------------------------------------------------------------

def test_user_input_is_html_escaped(client, make_ticket):
    ticket_id = make_ticket(title="<script>alert(1)</script>")
    for url in ("/", f"/tickets/{ticket_id}"):
        data = client.get(url).data
        assert b"<script>alert(1)</script>" not in data
        assert b"&lt;script&gt;" in data
