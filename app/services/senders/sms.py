
"""SMS sender. Uses a console transport for development."""

import logging

from app.models.notification import Notification
from app.services.senders.base import ChannelSender

logger = logging.getLogger(__name__)


class SMSSender(ChannelSender):
    """
    Sends SMS notifications.

    Currently uses a console transport for development. To connect a
    real provider (Twilio, Africa's Talking), replace the _transport
    method. The interface stays the same.
    """

    async def send(self, notification: Notification) -> None:
        await self._transport(notification)

    async def _transport(self, notification: Notification) -> None:
        """Actual delivery. Replace this to use a real provider."""
        # Validate recipient looks like a phone number
        if not notification.recipient.replace("+", "").replace("-", "").isdigit():
            raise ValueError(f"Invalid phone number: {notification.recipient}")

        logger.info(
            f"[SMS] to={notification.recipient} "
            f"body={notification.body!r}"
        )
