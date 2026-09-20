

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationChannel, NotificationStatus


class NotificationCreate(BaseModel):
   # """Request body for POST /notifications."""

    channel: NotificationChannel
    recipient: str = Field(..., min_length=1, max_length=255)
    subject: Optional[str] = Field(None, max_length=255)
    body: str = Field(..., min_length=1)


class DeliveryAttemptResponse(BaseModel):
    #Nested response for a single delivery attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt_number: int
    status: str
    error: Optional[str]
    attempted_at: datetime


class NotificationResponse(BaseModel):
    """Response body for a notification."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: NotificationChannel
    recipient: str
    subject: Optional[str]
    body: str
    status: NotificationStatus
    attempts: int
    last_error: Optional[str]
    created_at: datetime
    attempts_log: list[DeliveryAttemptResponse] = []
