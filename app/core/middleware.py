"""HTTP middleware for request IDs and logging."""

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variable so any code in the request path can access the ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID (or empty string if not in a request)."""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assign a unique ID to every request.

    The ID is:
    - Taken from the X-Request-ID header if the client provides one
    - Otherwise generated (UUID4)
    - Stored in a context var so logs and the worker can access it
    - Echoed back in the X-Request-ID response header
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(request_id)

        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
            },
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
            },
        )
        return response
