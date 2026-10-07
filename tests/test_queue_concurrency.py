
"""Prove the queue claim is concurrency-safe."""

import asyncio

import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationStatus,
)
from app.services.queue import claim_next_notification


@pytest_asyncio.fixture
async def five_pending_jobs(db_session):
    """Seed 5 pending notifications, clean up after."""
    await db_session.execute(delete(Notification))
    await db_session.commit()

    for i in range(5):
        db_session.add(
            Notification(
                channel=NotificationChannel.EMAIL,
                recipient=f"test{i}@example.com",
                body=f"test body {i}",
                status=NotificationStatus.PENDING,
            )
        )
    await db_session.commit()

    yield

    await db_session.execute(delete(Notification))
    await db_session.commit()


async def _worker(worker_id: str, results: list):
    """Simulate one worker with its own engine+session, in its own loop."""
    engine = create_async_engine(settings.TEST_DATABASE_URL, echo=False)
    SessionFactory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with SessionFactory() as db:
            claimed = await claim_next_notification(db, worker_id)
            results.append((worker_id, claimed.id if claimed else None))
    finally:
        await engine.dispose()


async def test_concurrent_claims_are_unique(five_pending_jobs):
    """5 concurrent workers claim 5 distinct jobs."""
    results = []
    await asyncio.gather(*[_worker(f"worker-{i}", results) for i in range(5)])

    claimed_ids = [r[1] for r in results if r[1] is not None]
    assert len(claimed_ids) == 5, f"Expected 5 claims, got {len(claimed_ids)}"
    assert len(set(claimed_ids)) == 5, f"Duplicate claim: {claimed_ids}"


async def test_claims_are_ordered(five_pending_jobs, db_session):
    """Jobs are claimed oldest-first."""
    results = []
    for i in range(5):
        claimed = await claim_next_notification(db_session, f"worker-{i}")
        results.append(claimed.id if claimed else None)

    assert results == sorted(results), f"Order wrong: {results}"


async def test_empty_queue_returns_none(five_pending_jobs, db_session):
    """Claiming from an empty queue returns None."""
    for _ in range(5):
        await claim_next_notification(db_session, "drainer")

    result = await claim_next_notification(db_session, "late")
    assert result is None
