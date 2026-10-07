"""Webhook HMAC signing is deterministic and correct."""

from app.services.senders.webhook import WebhookSender


def test_signature_is_deterministic():
    body = b'{"test": "value"}'
    assert WebhookSender._sign(body) == WebhookSender._sign(body)


def test_signature_changes_with_body():
    assert WebhookSender._sign(b'{"a": 1}') != WebhookSender._sign(b'{"a": 2}')


def test_signature_is_hex_sha256():
    sig = WebhookSender._sign(b"data")
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)
