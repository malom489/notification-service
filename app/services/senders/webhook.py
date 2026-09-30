"""Webhook sender. HTTP POST with HMAC signing."""

import hashlib
import hmac
import json
import logging

import httpx

from app.core.config import settings
from app.models.notification import Notification
from app.services.senders.base import ChannelSender

logger = logging.getLogger(__name__)


class WebhookSender(ChannelSender):
    """
    Delivers notifications via HTTP POST to a client-provided URL.

    The payload is JSON. The request is signed with HMAC-SHA256
    so the receiver can verify authenticity.
    """

    async def send(self, notification: Notification) -> None:
        if not settings.WEBHOOK_SECRET:
            raise ValueError("WEBHOOK_SECRET not configured")

        payload = {
            "notification_id": notification.id,
            "channel": notification.channel.value,
            "recipient": notification.recipient,
            "subject": notification.subject,
            "body": notification.body,
            "created_at": notification.created_at.isoformat(),
        }

        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = self._sign(body_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Id": str(notification.id),
            "X-Webhook-Signature": f"sha256={signature}",
            "User-Agent": "NotificationService/0.1",
        }

        logger.info(f"[WEBHOOK] POST to {notification.recipient}")

        async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
            response = await client.post(
                notification.recipient,
                content=body_bytes,
                headers=headers,
            )
            response.raise_for_status()

        logger.info(
            f"[WEBHOOK] Delivered to {notification.recipient} "
            f"(status={response.status_code})"
        )

    @staticmethod
    def _sign(body: bytes) -> str:
        """HMAC-SHA256 signature of the request body."""
        return hmac.new(
            settings.WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
