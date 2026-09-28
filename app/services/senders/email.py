"""Email sender via aiosmtplib. Delivers through Mailtrap Sandbox."""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.models.notification import Notification
from app.services.senders.base import ChannelSender

logger = logging.getLogger(__name__)


class EmailSender(ChannelSender):
    """Delivers notifications via SMTP. Raises on failure."""

    async def send(self, notification: Notification) -> None:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            raise ValueError("SMTP credentials not configured in .env")

        message = EmailMessage()
        message["From"] = settings.EMAIL_FROM
        message["To"] = notification.recipient
        message["Subject"] = notification.subject or "(no subject)"
        message.set_content(notification.body)

        logger.info(f"Sending email to {notification.recipient} via {settings.SMTP_HOST}")

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            timeout=10,
            
        )

        logger.info(f"Email sent to {notification.recipient}")
