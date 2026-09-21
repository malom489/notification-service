#queue operations 

from datetime import datetime

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

    The claim is a single UPDATE with a FOR UPDATE SKIP LOCKED subquery.
    Two workers calling this concurrently will receive different rows.
    """
    # Subquery: find the oldest eligible pending notification, lock it
    subquery = (
        select(Notification.id)
        .where(
            Notification.status == NotificationStatus.PENDING,
            Notification.scheduled_for <= func.now(),
        )
        .order_by(Notification.scheduled_for)
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    # Outer UPDATE: set it to processing, tag the worker, return the row
    stmt = (
        update(Notification)
        .where(Notification.id.in_(subquery))
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
