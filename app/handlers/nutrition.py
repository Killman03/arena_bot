from __future__ import annotations

from datetime import date

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.models import MealPlan, MealType, User
from app.db.session import session_scope

router = Router()


@router.message(Command("meal"))
async def plan_meal(message: types.Message) -> None:
    """Plan a meal: /meal breakfast Омлет [YYYY-MM-DD]."""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/meal", "", 1).strip()
    if not payload:
        await message.answer("Использование: /meal breakfast Название [YYYY-MM-DD]")
        return
    parts = payload.split()
    meal_type = MealType(parts[0])
    title = " ".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
    d = parts[-1]
    try:
        plan_date = date.fromisoformat(d)
    except Exception:
        plan_date = date.today()
        title = " ".join(parts[1:])

    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        session.add(MealPlan(user_id=db_user.id, date=plan_date, type=meal_type, title=title))
    await message.answer("Прием пищи запланирован ✅")



