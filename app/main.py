

from fastapi import FastAPI

from app.api.v1.api import router as v1_router
from app.core.config import settings
from app.core.handlers import register_exception_handlers

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

register_exception_handlers(app)

app.include_router(v1_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health():
    """Health check for load balancers and monitoring."""
    return {"status": "ok", "service": settings.PROJECT_NAME}
