"""Idempotency key behavior."""


async def test_same_key_same_body_returns_original(client):
    """Same key + same body returns the original notification."""
    key = "test-idem-1"
    payload = {"channel": "email", "recipient": "a@b.com", "body": "hello"}

    r1 = await client.post(
        "/api/v1/notifications/",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    r2 = await client.post(
        "/api/v1/notifications/",
        json=payload,
        headers={"Idempotency-Key": key},
    )

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["id"] == r2.json()["id"]


async def test_same_key_different_body_returns_409(client):
    """Same key + different body returns 409 Conflict."""
    key = "test-idem-2"

    await client.post(
        "/api/v1/notifications/",
        json={"channel": "email", "recipient": "a@b.com", "body": "first"},
        headers={"Idempotency-Key": key},
    )

    r = await client.post(
        "/api/v1/notifications/",
        json={"channel": "email", "recipient": "a@b.com", "body": "second"},
        headers={"Idempotency-Key": key},
    )

    assert r.status_code == 409
    assert r.json()["error"] == "idempotency_key_conflict"


async def test_no_key_creates_new_each_time(client):
    """Without a key, identical requests create two notifications."""
    payload = {"channel": "email", "recipient": "a@b.com", "body": "dup"}

    r1 = await client.post("/api/v1/notifications/", json=payload)
    r2 = await client.post("/api/v1/notifications/", json=payload)

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["id"] != r2.json()["id"]
