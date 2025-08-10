from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    User,
    Interaction,
    Goal,
    Habit,
    HabitLog,
    FinanceTransaction,
    PomodoroSession,
)


async def export_user_data_to_csv(session: AsyncSession, user_id: int, out_dir: Path) -> dict[str, Path]:
    """Export key entities to CSV files; returns mapping entity -> path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    exports: dict[str, Path] = {}

    async def _dump(query, filename: str) -> Path:
        result = await session.execute(query)
        rows = [row.__dict__ for row in result.scalars().all()]
        for r in rows:
            r.pop("_sa_instance_state", None)
        df = pd.DataFrame(rows)
        path = out_dir / filename
        df.to_csv(path, index=False)
        return path

    exports["interactions"] = await _dump(select(Interaction).where(Interaction.user_id == user_id), "interactions.csv")
    exports["goals"] = await _dump(select(Goal).where(Goal.user_id == user_id), "goals.csv")
    exports["habits"] = await _dump(select(Habit).where(Habit.user_id == user_id), "habits.csv")
    exports["habit_logs"] = await _dump(
        select(HabitLog).where(HabitLog.habit_id.in_(select(Habit.id).where(Habit.user_id == user_id))),
        "habit_logs.csv",
    )
    exports["finance"] = await _dump(select(FinanceTransaction).where(FinanceTransaction.user_id == user_id), "finance.csv")
    exports["pomodoro"] = await _dump(select(PomodoroSession).where(PomodoroSession.user_id == user_id), "pomodoro.csv")

    return exports


async def export_user_data_to_excel(session: AsyncSession, user_id: int, out_file: Path) -> Path:
    """Export key entities to a single Excel workbook with multiple sheets."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        async def _sheet(query, sheet: str) -> None:
            result = await session.execute(query)
            rows = [row.__dict__ for row in result.scalars().all()]
            for r in rows:
                r.pop("_sa_instance_state", None)
            pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, index=False)

        await _sheet(select(Interaction).where(Interaction.user_id == user_id), "interactions")
        await _sheet(select(Goal).where(Goal.user_id == user_id), "goals")
        await _sheet(select(Habit).where(Habit.user_id == user_id), "habits")
        await _sheet(
            select(HabitLog).where(HabitLog.habit_id.in_(select(Habit.id).where(Habit.user_id == user_id))),
            "habit_logs",
        )
        await _sheet(select(FinanceTransaction).where(FinanceTransaction.user_id == user_id), "finance")
        await _sheet(select(PomodoroSession).where(PomodoroSession.user_id == user_id), "pomodoro")

    return out_file



