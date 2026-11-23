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


# ---- assigned engineer -----------------------------------------------------

def test_index_filter_by_engineer(client, make_ticket):
    make_ticket(title="AlexTicket", engineer="Alex")
    make_ticket(title="SamTicket", engineer="Sam")
    data = client.get("/?engineer=Alex").data
    assert b"AlexTicket" in data
    assert b"SamTicket" not in data


def test_index_filter_unassigned(client, make_ticket):
    make_ticket(title="AlexTicket", engineer="Alex")
    make_ticket(title="NobodyTicket")
    data = client.get(f"/?engineer={models.UNASSIGNED}").data
    assert b"NobodyTicket" in data
    assert b"AlexTicket" not in data


def test_index_filter_status_and_engineer(client, make_ticket):
    make_ticket(title="Hit", engineer="Alex", status="Closed")
    make_ticket(title="Miss", engineer="Alex")
    data = client.get("/?status=Closed&engineer=Alex").data
    assert b"Hit" in data and b"Miss" not in data


def test_index_dropdown_lists_engineers(client, make_ticket):
    make_ticket(engineer="Alex Morgan")
    data = client.get("/").data
    assert b'value="Alex Morgan"' in data
    assert b"Unassigned" in data


def test_create_with_engineer(client):
    client.post("/tickets/new", data={**VALID, "assigned_engineer": "  Alex  "})
    assert models.get_ticket(1)["assigned_engineer"] == "Alex"


def test_create_without_engineer_is_unassigned(client):
    client.post("/tickets/new", data=VALID)
    assert models.get_ticket(1)["assigned_engineer"] is None


def test_create_engineer_too_long_rejected(client):
    response = client.post("/tickets/new", data={**VALID, "assigned_engineer": "x" * 101})
    assert b"Engineer name must be at most 100" in response.data
    assert models.list_tickets() == []


def test_detail_shows_engineer_or_unassigned(client, make_ticket):
    assigned = make_ticket(engineer="Alex Morgan")
    nobody = make_ticket()
    assert b"Alex Morgan" in client.get(f"/tickets/{assigned}").data
    assert b"Unassigned" in client.get(f"/tickets/{nobody}").data


def test_assign_engineer_route(client, make_ticket):
    ticket_id = make_ticket()
    response = client.post(f"/tickets/{ticket_id}/engineer", data={"assigned_engineer": " Sam "})
    assert response.status_code == 302
    assert models.get_ticket(ticket_id)["assigned_engineer"] == "Sam"


def test_assign_empty_unassigns(client, make_ticket):
    ticket_id = make_ticket(engineer="Sam")
    client.post(f"/tickets/{ticket_id}/engineer", data={"assigned_engineer": ""})
    assert models.get_ticket(ticket_id)["assigned_engineer"] is None


def test_assign_too_long_rejected(client, make_ticket):
    ticket_id = make_ticket(engineer="Sam")
    response = client.post(
        f"/tickets/{ticket_id}/engineer",
        data={"assigned_engineer": "x" * 101}, follow_redirects=True,
    )
    assert b"at most 100" in response.data
    assert models.get_ticket(ticket_id)["assigned_engineer"] == "Sam"


def test_assign_unknown_ticket_is_404(client):
    assert client.post("/tickets/999/engineer", data={"assigned_engineer": "x"}).status_code == 404


def test_engineer_name_is_html_escaped(client, make_ticket):
    ticket_id = make_ticket(engineer="<script>alert(1)</script>")
    for url in ("/", f"/tickets/{ticket_id}"):
        data = client.get(url).data
        assert b"<script>alert(1)</script>" not in data
        assert b"&lt;script&gt;" in data


# ---- priority filter -------------------------------------------------------

def test_index_filter_by_priority(client, make_ticket):
    make_ticket(title="HighOne", priority="High")
    make_ticket(title="LowOne", priority="Low")
    data = client.get("/?priority=High").data
    assert b"HighOne" in data and b"LowOne" not in data


def test_index_invalid_priority_shows_all(client, make_ticket):
    make_ticket(title="HighOne", priority="High")
    make_ticket(title="LowOne", priority="Low")
    data = client.get("/?priority=bogus").data
    assert b"HighOne" in data and b"LowOne" in data


def test_index_all_three_filters_combine(client, make_ticket):
    make_ticket(title="Hit", priority="High", engineer="Alex", status="Closed")
    make_ticket(title="Miss", priority="Low", engineer="Alex", status="Closed")
    data = client.get("/?status=Closed&engineer=Alex&priority=High").data
    assert b"Hit" in data and b"Miss" not in data


def test_priority_dropdown_has_options_and_selection(client):
    data = client.get("/?priority=Medium").data.decode()
    for label in ("All priorities", "Low", "Medium", "High"):
        assert label in data
    assert 'value="Medium" selected' in data


def test_status_links_keep_priority_filter(client):
    data = client.get("/?priority=High&engineer=Alex").data.decode()
    for status in ("Open", "In+Progress", "Closed"):
        assert f"status={status}&amp;engineer=Alex&amp;priority=High" in data
    assert "/?engineer=Alex&amp;priority=High" in data  # the "All" button
