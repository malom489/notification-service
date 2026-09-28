"""Classify delivery errors as retryable or terminal."""

import smtplib


# Errors that should NEVER be retried. The problem won't go away.
TERMINAL_EXCEPTIONS = (
    smtplib.SMTPAuthenticationError,     # Bad SMTP credentials
    smtplib.SMTPRecipientsRefused,       # Recipient rejected
    smtplib.SMTPSenderRefused,           # Sender rejected
    smtplib.SMTPDataError,               # Data rejected (malformed)
    ValueError,                          # Our own validation errors
)


def is_retryable(error: Exception) -> bool:
    """
    Return True if the error is worth retrying.

    Default: retry everything that isn't explicitly terminal.
    Rationale: transient network errors are more common than
    permanent failures, and a wasted retry is cheaper than a lost
    notification.
    """
    return not isinstance(error, TERMINAL_EXCEPTIONS)
