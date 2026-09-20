

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppException,
    NotificationNotFoundError,
    InvalidIdempotencyKeyError,
    InvalidChannelError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers."""

    @app.exception_handler(NotificationNotFoundError)
    async def notification_not_found(request: Request, exc: NotificationNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "notification_not_found",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InvalidIdempotencyKeyError)
    async def invalid_idempotency_key(request: Request, exc: InvalidIdempotencyKeyError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "idempotency_key_conflict",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(InvalidChannelError)
    async def invalid_channel(request: Request, exc: InvalidChannelError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "invalid_channel",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AppException)
    async def generic_app_exception(request: Request, exc: AppException):
        logger.warning(f"Unhandled AppException: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred.",
                "details": {},
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred.",
                "details": {},
            },
        )
