from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Habit, HabitLog
from app.db.models.finance import FinanceTransaction


async def plot_weekly_habit_completion(session: AsyncSession, user_id: int, out_file: Path) -> Path:
    """Render a bar chart of habit completion counts for the last 7 days."""
    today = date.today()
    start = today - timedelta(days=6)

    q = (
        select(Habit.name, HabitLog.date, func.sum(HabitLog.value))
        .join(HabitLog, HabitLog.habit_id == Habit.id)
        .where(Habit.user_id == user_id, HabitLog.date.between(start, today))
        .group_by(Habit.name, HabitLog.date)
        .order_by(HabitLog.date)
    )
    result = await session.execute(q)
    rows = result.all()

    if not rows:
        # Create empty plot
        plt.figure(figsize=(8, 4))
        plt.title("No habit data for the last 7 days")
        plt.savefig(out_file, bbox_inches="tight")
        plt.close()
        return out_file

    # Aggregate by date
    dates = [start + timedelta(days=i) for i in range(7)]
    per_day = {d: 0.0 for d in dates}
    for _, d, val in rows:
        per_day[d] = per_day.get(d, 0.0) + float(val or 0.0)

    plt.figure(figsize=(10, 4))
    plt.bar([d.strftime("%d.%m") for d in dates], list(per_day.values()))
    plt.title("Habit completion (last 7 days)")
    plt.xlabel("Date")
    plt.ylabel("Sum value")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, bbox_inches="tight")
    plt.close()
    return out_file


async def plot_monthly_spending(session: AsyncSession, user_id: int, year: int, month: int, out_file: Path) -> Path:
    """Render a pie chart of spending by category for a given month."""
    from datetime import date

    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    q = (
        select(FinanceTransaction.category, func.sum(FinanceTransaction.amount))
        .where(
            FinanceTransaction.user_id == user_id,
            FinanceTransaction.date >= start,
            FinanceTransaction.date < end,
        )
        .group_by(FinanceTransaction.category)
    )
    result = await session.execute(q)
    rows = result.all()

    labels = [r[0] for r in rows]
    values = [float(r[1]) for r in rows]
    if not values:
        labels = ["Нет данных"]
        values = [1]

    plt.figure(figsize=(6, 6))
    plt.pie(values, labels=labels, autopct="%1.1f%%")
    plt.title(f"Расходы за {month:02d}.{year}")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, bbox_inches="tight")
    plt.close()
    return out_file


