from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.models import PomodoroSession, User
from app.db.session import session_scope

router = Router()


@router.message(Command("pomodoro"))
async def start_pomodoro(message: types.Message) -> None:
    """Start a 25-minute pomodoro."""
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        session.add(PomodoroSession(user_id=db_user.id))
    await message.answer("Помодоро начат на 25 минут. Фокус!")






