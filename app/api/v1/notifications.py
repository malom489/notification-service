
"""Notification endpoints."""

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    InvalidIdempotencyKeyError,
    NotificationNotFoundError,
)
from app.db.session import get_db
from app.models.notification import Notification, NotificationStatus
from app.schemas.notification import NotificationCreate, NotificationResponse

router = APIRouter()


async def _find_by_idempotency_key(
    db: AsyncSession, key: str
) -> Notification | None:
    """Fetch a notification by idempotency key, with attempts loaded."""
    result = await db.execute(
        select(Notification)
        .where(Notification.idempotency_key == key)
        .options(selectinload(Notification.attempts_log))
    )
    return result.scalar_one_or_none()


def _assert_same_payload(
    existing: Notification,
    incoming: NotificationCreate,
    key: str,
) -> None:
    """Raise 409 if the same key is used with different content."""
    if (
        existing.channel != incoming.channel
        or existing.recipient != incoming.recipient
        or existing.subject != incoming.subject
        or existing.body != incoming.body
    ):
        raise InvalidIdempotencyKeyError(
            message="Idempotency-Key reused with a different payload.",
            details={"idempotency_key": key},
        )


@router.post(
    "/",
    response_model=NotificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_notification(
    notification_in: NotificationCreate,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a notification request and store it for async delivery.

    If an Idempotency-Key header is provided:
    - Same key + same body: returns the original notification
    - Same key + different body: returns 409 Conflict
    """
    # Fast path: key already exists
    if idempotency_key:
        existing = await _find_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            _assert_same_payload(existing, notification_in, idempotency_key)
            return existing

    # Create new notification
    notification = Notification(
        channel=notification_in.channel,
        recipient=notification_in.recipient,
        subject=notification_in.subject,
        body=notification_in.body,
        status=NotificationStatus.PENDING,
        idempotency_key=idempotency_key,
    )
    db.add(notification)

    try:
        await db.flush()
    except IntegrityError:
        # Race: another request with the same key inserted first
        await db.rollback()
        if not idempotency_key:
            raise
        existing = await _find_by_idempotency_key(db, idempotency_key)
        if existing is None:
            raise
        _assert_same_payload(existing, notification_in, idempotency_key)
        return existing

    # Re-fetch with relationship eager-loaded
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
