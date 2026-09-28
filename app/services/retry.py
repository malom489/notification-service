"""Retry scheduling with exponential backoff and jitter."""

import random
from datetime import datetime, timedelta, timezone

from app.core.config import settings


def calculate_next_retry(attempts: int) -> datetime:
    """
    Calculate when the next retry should happen.

    Formula: min(max_delay, base * 2^(attempts - 1)) + jitter

    The exponential term grows the delay each time.
    The jitter term spreads simultaneous retries so they don't
    all hit the provider at the same second.
    """
    exponential = settings.RETRY_BASE_DELAY_SECONDS * (2 ** (attempts - 1))
    capped = min(exponential, settings.RETRY_MAX_DELAY_SECONDS)
    jitter = random.uniform(0, settings.RETRY_JITTER_MAX_SECONDS)

    delay_seconds = capped + jitter
    return datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
