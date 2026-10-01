"""Metrics endpoint for Prometheus scraping."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import metrics
from app.db.session import get_db
from app.models.notification import Notification, NotificationStatus

router = APIRouter()


@router.get("")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """
    Return Prometheus-format metrics.

    Includes both in-memory counters and current DB state
    (queue depth by status).
    """
    # Queue depth by status
    result = await db.execute(
        select(Notification.status, func.count(Notification.id))
        .group_by(Notification.status)
    )
    for status, count in result.all():
        metrics.set_gauge(
            "notifications_queue_depth",
            count,
            labels={"status": status.value},
        )

    return Response(
        content=metrics.render(),
        media_type="text/plain; version=0.0.4",
    )
