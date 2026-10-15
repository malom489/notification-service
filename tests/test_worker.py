
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


def _mock_session_with(notification):
    """Build a mock session that returns the given notification from get()."""
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=notification)

    # execute() returns a mock; rowcount=1 simulates "we held the lease"
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()
    return mock_db


async def test_process_one_empty_queue():
    """When the queue is empty, process_one returns False."""
    mock_db = _mock_session_with(None)

    with patch("app.workers.worker.SessionLocal") as mock_session_cls, \
         patch("app.workers.worker.claim_next_notification",
               new_callable=AsyncMock, return_value=None):
        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        from app.workers.worker import process_one
        result = await process_one("test-worker")

    assert result is False


async def test_process_one_success(fake_sender):
    """A successful send stages a DeliveryAttempt and commits."""
    notification = _make_notification()
    mock_db = _mock_session_with(notification)

    with patch("app.workers.worker.SessionLocal") as mock_session_cls, \
         patch("app.workers.worker.claim_next_notification",
               new_callable=AsyncMock, return_value=notification), \
         patch("app.workers.worker.get_sender", return_value=fake_sender):

        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        from app.workers.worker import process_one
        result = await process_one("test-worker")

    assert result is True
    fake_sender.send.assert_awaited_once_with(notification)
    mock_db.add.assert_called_once()       # staged DeliveryAttempt
    mock_db.commit.assert_awaited()        # committed


async def test_process_one_retryable_failure(failing_sender):
    """A retryable failure stages a retry (execute called with PENDING status)."""
    notification = _make_notification()
    mock_db = _mock_session_with(notification)

    with patch("app.workers.worker.SessionLocal") as mock_session_cls, \
         patch("app.workers.worker.claim_next_notification",
               new_callable=AsyncMock, return_value=notification), \
         patch("app.workers.worker.get_sender", return_value=failing_sender):

        mock_session_cls.return_value.__aenter__.return_value = mock_db
        mock_session_cls.return_value.__aexit__.return_value = None

        from app.workers.worker import process_one
        result = await process_one("test-worker")

    assert result is True

    # Inspect the UPDATE statement that was executed
    assert mock_db.execute.await_count >= 1
    # The values passed to the UPDATE should include status=PENDING
    # and attempts=1 (the retry branch)
    update_stmt = mock_db.execute.await_args_list[0].args[0]
    params = update_stmt.compile().params
    assert params.get("status") == NotificationStatus.PENDING
    assert params.get("attempts") == 1
    assert "scheduled_for" in params  # retry scheduled for later
