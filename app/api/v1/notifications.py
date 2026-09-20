
"""Notification endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotificationNotFoundError
from app.db.session import get_db
from app.models.notification import Notification, NotificationStatus
from app.schemas.notification import NotificationCreate, NotificationResponse

router = APIRouter()


@router.post(
    "/",
    response_model=NotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_notification(
    notification_in: NotificationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Accept a notification request and store it for async delivery."""
    notification = Notification(
        channel=notification_in.channel,
        recipient=notification_in.recipient,
        subject=notification_in.subject,
        body=notification_in.body,
        status=NotificationStatus.PENDING,
    )
    db.add(notification)
    await db.flush()

    # Re-fetch with eager-loaded relationship
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification.id)
        .options(selectinload(Notification.attempts_log))
    )
    return result.scalar_one()


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
)
async def get_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a notification by ID, including its delivery attempts."""
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id)
        .options(selectinload(Notification.attempts_log))
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise NotificationNotFoundError(
            message=f"Notification {notification_id} not found.",
            details={"notification_id": notification_id},
        )

    return notification
