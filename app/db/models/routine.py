from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class RoutineType(str, Enum):
    morning = "morning"
    evening = "evening"


class RoutineChecklist(Base):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    type: Mapped[RoutineType] = mapped_column(SAEnum(RoutineType), index=True)
    title: Mapped[str] = mapped_column(String(128))


class RoutineItem(Base):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("routinechecklist.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(256))
    sort_order: Mapped[int] = mapped_column(default=0)


class RoutineLog(Base):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("routineitem.id", ondelete="CASCADE"), index=True)
    date: Mapped[date]
    completed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)



