
"""Integration tests for the notifications API."""


async def test_create_notification(client):
    """POST returns 202 with a pending notification."""
    response = await client.post(
        "/api/v1/notifications/",
        json={
            "channel": "email",
            "recipient": "test@example.com",
            "subject": "Test",
            "body": "Test body",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["channel"] == "email"
    assert data["status"] == "pending"
    assert data["attempts"] == 0


async def test_get_notification(client):
    """GET returns the created notification."""
    create_resp = await client.post(
        "/api/v1/notifications/",
        json={"channel": "email", "recipient": "x@y.com", "body": "hi"},
    )
    nid = create_resp.json()["id"]

    response = await client.get(f"/api/v1/notifications/{nid}")
    assert response.status_code == 200
    assert response.json()["id"] == nid


async def test_get_missing_notification(client):
    """GET for a missing ID returns 404 with our error shape."""
    response = await client.get("/api/v1/notifications/99999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "notification_not_found"
    assert data["details"]["notification_id"] == 99999


async def test_invalid_channel(client):
    """POST with an unsupported channel returns 422."""
    response = await client.post(
        "/api/v1/notifications/",
        json={"channel": "telegram", "recipient": "x", "body": "y"},
    )
    assert response.status_code == 422


async def test_empty_body_rejected(client):
    """POST with an empty body returns 422."""
    response = await client.post(
        "/api/v1/notifications/",
        json={"channel": "email", "recipient": "x", "body": ""},
    )
    assert response.status_code == 422
