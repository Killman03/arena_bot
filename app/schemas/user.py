from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    timezone: str = Field(default="UTC")


class UserRead(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    timezone: str
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class InteractionCreate(BaseModel):
    message_text: Optional[str] = None
    command: Optional[str] = None
    metadata: dict = Field(default_factory=dict)



