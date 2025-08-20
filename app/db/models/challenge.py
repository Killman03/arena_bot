from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import ForeignKey, String, Date
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Challenge(Base):
    """User-defined daily challenges with a reminder time."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    time_str: Mapped[str] = mapped_column(String(5), default="07:00")  # HH:MM
    is_active: Mapped[bool] = mapped_column(default=True)
    # Mon..Sun mask (1=notify, 0=skip). Default: 1111110 (daily except Sunday)
    days_mask: Mapped[str] = mapped_column(String(7), default="1111110")
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # Дата окончания челленджа
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ChallengeLog(Base):
    """Completion log for challenge per day."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenge.id", ondelete="CASCADE"), index=True)
    date: Mapped[date]
    completed: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


