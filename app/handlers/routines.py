from __future__ import annotations

from datetime import date

from aiogram import Router, types
from aiogram.filters import Command

from app.db.session import session_scope
from app.db.models import RoutineLog, RoutineItem, User

router = Router()


@router.message(Command("check"))
async def check_item(message: types.Message) -> None:
    """Mark routine item completed: /check item_id [YYYY-MM-DD]."""
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /check item_id [YYYY-MM-DD]")
        return
    item_id = int(parts[1])
    check_date = date.fromisoformat(parts[2]) if len(parts) > 2 else date.today()
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        # Ensure item exists
        item = await session.get(RoutineItem, item_id)
        if item is None:
            await message.answer("Пункт не найден")
            return
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        session.add(RoutineLog(user_id=db_user.id, item_id=item_id, date=check_date, completed=True))
    await message.answer("Отмечено ✅")


