
"""Tests for the worker's per-job processing logic.

These tests mock the database session to isolate process_one's logic.
Real database behavior is covered in test_queue_concurrency.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
)
from app.services.senders.base import ChannelSender


@pytest.fixture
def fake_sender():
    """A sender that always succeeds."""
    sender = AsyncMock(spec=ChannelSender)
    sender.send = AsyncMock(return_value=None)
    return sender


@pytest.fixture
def failing_sender():
    """A sender that raises a retryable error."""
    sender = AsyncMock(spec=ChannelSender)
    sender.send = AsyncMock(side_effect=RuntimeError("network blip"))
    return sender


def _make_notification() -> Notification:
    return Notification(
        id=1,
        channel=NotificationChannel.EMAIL,
        recipient="test@example.com",
        body="test",
        status=NotificationStatus.PENDING,
        attempts=0,
    )


async def test_process_one_empty_queue():
    """When the queue is empty, process_one returns False."""
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=None)

    with patch("app.workers.worker.SessionLocal") as mock_session_cls, \
         patch("app.workers.worker.claim_next_notification", new_callable=AsyncMock, return_value=None):
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        from app.workers.worker import process_one
        result = await process_one("test-worker")

    assert result is False


async def test_process_one_success(fake_sender):
    """A successful send records the attempt and marks SENT."""
    notification = _make_notification()
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=notification)

    with patch("app.workers.worker.SessionLocal") as mock_session_cls, \
         patch("app.workers.worker.claim_next_notification", new_callable=AsyncMock, return_value=notification), \
         patch("app.workers.worker.get_sender", return_value=fake_sender):

        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        from app.workers.worker import process_one
        result = await process_one("test-worker")

    assert result is True
    # The sender was called
    fake_sender.send.assert_awaited_once_with(notification)
    # A DeliveryAttempt was added
    mock_db.add.assert_called_once()
    # The commit was called
    mock_db.commit.assert_awaited()


async def test_process_one_retryable_failure(failing_sender):
    """A retryable failure schedules a retry (status stays PENDING)."""
    notification = _make_notification()
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=notification)

    with patch("app.workers.worker.SessionLocal") as mock_session_cls, \
         patch("app.workers.worker.claim_next_notification", new_callable=AsyncMock, return_value=notification), \
         patch("app.workers.worker.get_sender", return_value=failing_sender):

        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        from app.workers.worker import process_one
        result = await process_one("test-worker")

    assert result is True
    # Status is back to PENDING (retry scheduled)
    assert notification.status == NotificationStatus.PENDING
    assert notification.attempts == 1
    assert notification.last_error is not None
