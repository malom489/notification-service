"""Channel sender registry. Maps channel type to sender instance."""

from app.models.notification import NotificationChannel
from app.services.senders.base import ChannelSender
from app.services.senders.email import EmailSender
from app.services.senders.sms import SMSSender
from app.services.senders.webhook import WebhookSender

_SENDERS: dict[NotificationChannel, ChannelSender] = {
    NotificationChannel.EMAIL: EmailSender(),
    NotificationChannel.SMS: SMSSender(),
    NotificationChannel.WEBHOOK: WebhookSender(),
}


def get_sender(channel: NotificationChannel) -> ChannelSender:
    """Get the sender for a channel. Raises KeyError if unknown."""
    return _SENDERS[channel]
