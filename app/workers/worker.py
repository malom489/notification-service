"""Notification worker. Claims jobs and delivers them."""

import asyncio
import logging
import os
import signal
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.notification import (
    DeliveryAttempt,
    Notification,
    NotificationStatus,
)
from app.services.queue import claim_next_notification
from app.services.senders import get_sender

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
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
    error: str | None,
) -> None:
    """Record the outcome of an attempt and update the notification."""
    attempt_number = notification.attempts + 1

    db.add(
        DeliveryAttempt(
            notification_id=notification.id,
            attempt_number=attempt_number,
            status="failed" if error else "success",
            error=error,
        )
    )

    notification.attempts = attempt_number
    notification.last_error = error

    if error:
        # M6 will add retry/backoff. For now, mark failed.
        notification.status = NotificationStatus.FAILED
    else:
        notification.status = NotificationStatus.SENT
        notification.locked_at = None
        notification.locked_by = None

    await db.commit()


async def process_one(worker_id: str) -> bool:
    """
    Claim and process one job. Returns True if a job was processed,
    False if the queue was empty.
    """
    # Phase 1: claim (short transaction)
    async with SessionLocal() as db:
        notification = await claim_next_notification(db, worker_id)

    if notification is None:
        return False

    logger.info(
        f"Claimed notification {notification.id} "
        f"(channel={notification.channel.value})"
    )

    # Phase 2: send — NO DB connection held during I/O
    sender = get_sender(notification.channel)
    error: str | None = None
    try:
        await sender.send(notification)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        logger.warning(f"Delivery failed for {notification.id}: {error}")

    # Phase 3: record result (short transaction)
    async with SessionLocal() as db:
        fresh = await db.get(Notification, notification.id)
        if fresh is None:
            logger.error(f"Notification {notification.id} disappeared")
            return True
        await _record_attempt(db, fresh, error)

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
