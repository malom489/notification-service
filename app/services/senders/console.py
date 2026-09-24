"""Console sender. Prints notifications to stdout. For development."""

import logging

from app.models.notification import Notification
from app.services.senders.base import channelSender

logger = logging.getLogger(__name__)


class ConsoleSender(channelSender):
    """Pretends to deliver. Useful for testing the worker loop."""

    async def send(self, notification: Notification) -> None:
        logger.info(
            f"[CONSOLE] channel={notification.channel.value} "
            f"to={notification.recipient} "
            f"body={notification.body!r}"
        )
