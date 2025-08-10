from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User

router = Router()


# Email settings removed


@router.message(Command("notify"))
async def toggle_notify(message: types.Message) -> None:
    """Toggle preferences. Usage: /notify daily_principle on|off"""
    user = message.from_user
    if not user:
        return
    args = (message.text or "").split()
    if len(args) < 3:
        await message.answer("Использование: /notify <key> on|off")
        return
    key = args[1]
    val = args[2].lower() in {"on", "true", "1"}
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        prefs = dict(db_user.notification_preferences or {})
        prefs[key] = val
        db_user.notification_preferences = prefs
    await message.answer(f"Параметр {key} = {val}")


