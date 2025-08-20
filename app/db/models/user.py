from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, JSON, String, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from ..base import Base


class User(Base):
    """Telegram user entity used across the app."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notification_preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Настройки бюджета питания
    food_budget_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # "percentage_income" или "fixed_amount"
    food_budget_percentage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Процент от дохода (1-100)
    food_budget_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)  # Фиксированная сумма

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    interactions = relationship("Interaction", back_populates="user")
    todos = relationship("Todo", back_populates="user")


