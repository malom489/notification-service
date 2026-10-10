
"""Notification worker. Claims jobs and delivers them."""

import asyncio
import logging
import os
import signal
import sys

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update   

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal
from app.models.notification import (
    DeliveryAttempt,
    Notification,
    NotificationStatus,
)
from app.services.queue import claim_next_notification
from app.services.retry import calculate_next_retry
from app.services.senders import get_sender
from app.services.senders.errors import is_retryable

setup_logging()

logger = logging.getLogger("worker")

# Graceful shutdown flag
SHUTTING_DOWN = False


def _handle_shutdown(signum, frame):
    """Set the shutdown flag. The loop exits on next iteration."""
    global SHUTTING_DOWN
    logger.info(f"Received signal {signum}. Shutting down gracefully...")
    SHUTTING_DOWN = True


async def _record_attempt(
    db: AsyncSession,
    notification: Notification,
    worker_id: str,
    error: str | None,
    is_retryable_error: bool = False,
) -> None:
    """Record the outcome of an attempt, but only if this worker still holds the lease."""
    attempt_number = notification.attempts + 1

    # The audit row is always staged: the send really happened.
    db.add(
        DeliveryAttempt(
            notification_id=notification.id,
            attempt_number=attempt_number,
            status="failed" if error else "success",
            error=error,
        )
    )

    # Step 1: each outcome only decides WHAT changes.
    if not error:
        outcome = "sent"
        values = dict(
            status=NotificationStatus.SENT,
            attempts=attempt_number,
            last_error=None,
            locked_at=None,
            locked_by=None,
        )
    elif is_retryable_error and attempt_number < settings.MAX_DELIVERY_ATTEMPTS:
        outcome = "retry"
        values = dict(
            status=NotificationStatus.PENDING,
            attempts=attempt_number,
            last_error=error,
            scheduled_for=calculate_next_retry(attempt_number),
            locked_at=None,
            locked_by=None,
        )
    else:
        outcome = "dead_letter"
        values = dict(
            status=NotificationStatus.DEAD_LETTER,
            attempts=attempt_number,
            last_error=error,
            locked_at=None,
            locked_by=None,
        )

    # Step 2: one fenced update for all outcomes.
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification.id,
            Notification.locked_by == worker_id,
        )
        .values(**values)
    )

    # Step 3: lost the lease? Keep the audit row, touch nothing else.
    if result.rowcount == 0:
        logger.warning(f"Lost lease on notification {notification.id}")
        await db.commit()
        return

    await db.commit()

    if outcome == "retry":
        logger.info(
            f"Scheduling retry for notification {notification.id} "
            f"(attempt {attempt_number} failed, next at {values['scheduled_for']})"
        )
    elif outcome == "dead_letter":
        logger.warning(
            f"Notification {notification.id} moved to DEAD_LETTER "
            f"(attempts={attempt_number}, error={error})"
        )


async def process_one(worker_id: str) -> bool:
    """
    Claim and process one job.

    Returns True if a job was processed, False if the queue was empty.
    """
    # Phase 1: claim (short transaction)
    async with SessionLocal() as db:
        notification = await claim_next_notification(db, worker_id)

    if notification is None:
        return False

    logger.info(
        f"Claimed notification {notification.id} "
        f"(channel={notification.channel.value}, "
        f"attempt={notification.attempts + 1})"
    )

    # Phase 2: send — NO DB connection held during I/O
    sender = get_sender(notification.channel)
    error: str | None = None
    retryable = False
    try:
        await sender.send(notification)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        retryable = is_retryable(e)
        logger.warning(
            f"Delivery failed for {notification.id}: {error} "
            f"(retryable={retryable})"
        )

    # Phase 3: record result (new session)
    async with SessionLocal() as db:
        fresh = await db.get(Notification, notification.id)
      
        if fresh is None:
            logger.error(f"Notification {notification.id} disappeared")
            return True
        await _record_attempt(db, fresh, worker_id, error, is_retryable_error=retryable)

    return True


async def run_worker() -> None:
    """Main worker loop."""
    worker_id = os.environ.get("WORKER_ID", settings.WORKER_ID)
    logger.info(f"Worker {worker_id} starting")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    while not SHUTTING_DOWN:
        try:
            processed = await process_one(worker_id)
            if not processed:
                await asyncio.sleep(1)
        except Exception as e:
            logger.exception(f"Unexpected error in worker loop: {e}")
            await asyncio.sleep(5)

    logger.info(f"Worker {worker_id} stopped")


def main():
    """Entry point."""
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
