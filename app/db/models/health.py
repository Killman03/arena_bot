from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class HealthMetric(Base):
    """Aggregated daily health metrics per user."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(index=True)

    steps: Mapped[Optional[int]] = mapped_column(nullable=True)
    calories: Mapped[Optional[int]] = mapped_column(nullable=True)
    sleep_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)
    heart_rate_resting: Mapped[Optional[int]] = mapped_column(nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(nullable=True)
    systolic: Mapped[Optional[int]] = mapped_column(nullable=True)
    diastolic: Mapped[Optional[int]] = mapped_column(nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class HealthGoal(Base):
    """Simple per-metric goals (e.g., 8000 steps/day)."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(32), index=True)  # steps|sleep|calories|weight|hr|bp
    period: Mapped[str] = mapped_column(String(16), default="daily")  # daily|weekly
    target_value: Mapped[float]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class HealthReminder(Base):
    """Daily reminder to log health metrics at a specific time."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True, unique=True)
    time_str: Mapped[str] = mapped_column(String(10), default="21:00")  # HH:MM
    is_active: Mapped[bool] = mapped_column(default=True)
    metrics_mask: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # e.g. "steps,sleep,weight"
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)





