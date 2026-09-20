


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NotificationNotFoundError(AppException):
    
    pass


class InvalidIdempotencyKeyError(AppException):
    
    pass


class InvalidChannelError(AppException):
    
    pass
