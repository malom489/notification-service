"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import notifications

router = APIRouter()

router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
)
