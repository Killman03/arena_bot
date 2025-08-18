from __future__ import annotations

from datetime import date
from pydantic import BaseModel

from app.db.models.habit import Periodicity


class HabitCreate(BaseModel):
    name: str
    periodicity: Periodicity = Periodicity.week
    target_value: float = 1.0
    schedule_mask: str = "1111100"  # Mon..Sun
    start_date: date


class HabitLogCreate(BaseModel):
    habit_id: int
    date: date
    value: float = 1.0
    note: str | None = None






