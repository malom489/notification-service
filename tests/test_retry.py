"""Retry backoff math and error classification."""

from datetime import datetime, timezone

from app.core.config import settings
from app.services.retry import calculate_next_retry
from app.services.senders.errors import is_retryable


def test_backoff_increases_with_attempts():
    """Retry delay grows with attempts."""
    now = datetime.now(timezone.utc)
    d1 = (calculate_next_retry(1) - now).total_seconds()
    d2 = (calculate_next_retry(2) - now).total_seconds()
    d3 = (calculate_next_retry(3) - now).total_seconds()

    assert 1.9 <= d1 <= 7.1
    assert 3.9 <= d2 <= 9.1
    assert 7.9 <= d3 <= 13.1


def test_retry_caps_at_max_delay():
    """Backoff doesn't exceed the max cap + jitter."""
    now = datetime.now(timezone.utc)
    delay = (calculate_next_retry(20) - now).total_seconds()
    cap = settings.RETRY_MAX_DELAY_SECONDS + settings.RETRY_JITTER_MAX_SECONDS
    assert delay <= cap


def test_value_error_is_terminal():
    assert is_retryable(ValueError("bad input")) is False


def test_generic_exception_is_retryable():
    assert is_retryable(RuntimeError("network")) is True
