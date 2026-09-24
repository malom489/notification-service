"""Channel sender registry. Maps channel type to sender instance."""

from app.models.notification import NotificationChannel
from app.services.senders.base import channelSender
from app.services.senders.console import ConsoleSender

# Instantiate senders once. They're stateless.
_SENDERS: dict[NotificationChannel, channelSender] = {
    NotificationChannel.EMAIL: ConsoleSender(),   # replace with EmailSender in M5
    NotificationChannel.SMS: ConsoleSender(),     # replace in M8
    NotificationChannel.WEBHOOK: ConsoleSender(), # replace in M8
}


def get_sender(channel: NotificationChannel) -> channelSender:
    """Get the sender for a channel. Raises KeyError if unknown."""
    return _SENDERS[channel]
