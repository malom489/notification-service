
"""Queue operations for claiming notifications."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationStatus


async def claim_next_notification(
    db: AsyncSession,
    worker_id: str,
) -> Notification | None:
    """
    Atomically claim the next eligible notification for processing.

    Returns the claimed Notification, or None if the queue is empty.

    Uses a scalar subquery (not IN) so the UPDATE matches exactly one
    row. FOR UPDATE SKIP LOCKED inside the subquery lets concurrent
    workers claim different rows without blocking.
    """
    # Scalar subquery: exactly one ID, or NULL
    subquery = (
        select(Notification.id)
        .where(
            Notification.status == NotificationStatus.PENDING,
            Notification.scheduled_for <= func.now(),
        )
        .order_by(Notification.scheduled_for)
        .with_for_update(skip_locked=True)
        .limit(1)
        .scalar_subquery()
    )

    stmt = (
        update(Notification)
        .where(Notification.id == subquery)
        .values(
            status=NotificationStatus.PROCESSING,
            locked_by=worker_id,
            locked_at=func.now(),
        )
        .returning(Notification)
    )

    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one_or_none()
