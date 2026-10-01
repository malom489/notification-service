
"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.v1.api import router as v1_router
from app.api.v1.metrics import router as metrics_router
from app.core.config import settings
from app.core.handlers import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Middleware runs BEFORE exception handlers see the request
app.add_middleware(RequestIDMiddleware)

register_exception_handlers(app)

app.include_router(v1_router, prefix=settings.API_V1_STR)
app.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.PROJECT_NAME}
