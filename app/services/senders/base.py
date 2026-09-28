
"""Abstract ChannelSender. All channels implement this interface."""

from abc import ABC, abstractmethod

from app.models.notification import Notification


class ChannelSender(ABC):
    """
    Abstract base for all channel senders.

    A sender's job: deliver the notification, or raise an exception.
    It never touches the database.
    """

    @abstractmethod
    async def send(self, notification: Notification) -> None:
        """
        Attempt to deliver the notification.

        Raises an exception on failure. Returns None on success.
        """
        raise NotImplementedError
