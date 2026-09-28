
"""Channel sender registry. Maps channel type to sender instance."""

from app.models.notification import NotificationChannel
from app.services.senders.base import ChannelSender
from app.services.senders.console import ConsoleSender
from app.services.senders.email import EmailSender

_SENDERS: dict[NotificationChannel, ChannelSender] = {
    NotificationChannel.EMAIL: EmailSender(),
    NotificationChannel.SMS: ConsoleSender(),
    NotificationChannel.WEBHOOK: ConsoleSender(),
}


def get_sender(channel: NotificationChannel) -> ChannelSender:
    """Get the sender for a channel. Raises KeyError if unknown."""
    return _SENDERS[channel]
