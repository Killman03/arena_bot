from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class GoalScope(str, Enum):
    five_years = "5y"
    year = "1y"
    month = "1m"
    week = "1w"
    three_months = "3m"
    six_months = "6m"
    day = "1d"


class GoalStatus(str, Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class Goal(Base):
    """User goals in a hierarchy with SMART-like fields."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    scope: Mapped[GoalScope] = mapped_column(SAEnum(GoalScope), index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    status: Mapped[GoalStatus] = mapped_column(SAEnum(GoalStatus), default=GoalStatus.active, index=True)

    # SMART criteria
    is_specific: Mapped[bool] = mapped_column(default=True)
    is_measurable: Mapped[bool] = mapped_column(default=True)
    is_achievable: Mapped[bool] = mapped_column(default=True)
    is_relevant: Mapped[bool] = mapped_column(default=True)
    time_bound: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)


class ABAnalysis(Base):
    """A/B analysis: current vs desired state per user."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    current_state: Mapped[str] = mapped_column(Text)
    desired_state: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class GoalReminder(Base):
    """Reminders for goals with motivational messages."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), index=True)
    reminder_time: Mapped[str] = mapped_column(String(5))  # Format: "HH:MM"
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    goal: Mapped[Goal] = relationship("Goal", back_populates="reminders")


# Добавляем обратную связь в Goal
Goal.reminders = relationship("GoalReminder", back_populates="goal", cascade="all, delete-orphan")






