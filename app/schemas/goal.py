from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel

from app.db.models.goal import GoalScope, GoalStatus


class GoalCreate(BaseModel):
    scope: GoalScope
    title: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    is_specific: bool = True
    is_measurable: bool = True
    is_achievable: bool = True
    is_relevant: bool = True
    time_bound: bool = True


class GoalRead(BaseModel):
    id: int
    scope: GoalScope
    title: str
    description: Optional[str]
    start_date: Optional[date]
    due_date: Optional[date]
    status: GoalStatus

    model_config = dict(from_attributes=True)


class ABAnalysisCreate(BaseModel):
    current_state: str
    desired_state: str



