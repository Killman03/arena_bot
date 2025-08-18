from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Periodicity(str, Enum):
    day = "day"
    week = "week"
    month = "month"


class Habit(Base):
    """Habit definition with target per period."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    periodicity: Mapped[Periodicity] = mapped_column(SAEnum(Periodicity), default=Periodicity.week)
    target_value: Mapped[float] = mapped_column(default=1.0)
    schedule_mask: Mapped[str] = mapped_column(String(32), default="1111100")  # Mon..Sun
    is_active: Mapped[bool] = mapped_column(default=True)
    start_date: Mapped[date] = mapped_column(default=date.today)


class HabitLog(Base):
    """Fact log for a habit: date and value (e.g., km, count, hours)."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habit.id", ondelete="CASCADE"), index=True)
    date: Mapped[date]
    value: Mapped[float] = mapped_column(default=1.0)
    note: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)






