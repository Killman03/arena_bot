from __future__ import annotations

from datetime import datetime
import random

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User
from app.db.models.motivation import Motivation

from app.services.reminders import LAWS_OF_ARENA

router = Router()


@router.message(Command("test_reminders"))
async def test_reminders(message: types.Message) -> None:
    """Manually test reminder deliveries for the current user."""
    user = message.from_user
    if not user:
        return

    sent = {"principle": False, "motivation": False}

    # Daily principle
    principle = random.choice(LAWS_OF_ARENA)
    try:
        await message.answer(f"Дневной принцип (тест):\n\n{principle}")
        sent["principle"] = True
    except Exception:
        pass

    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()

        # Motivation
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        texts = [t for t in [(mot.main_year_goal if mot else None), (mot.vision if mot else None), (mot.mission if mot else None), (mot.values if mot else None)] if t]
        if texts:
            try:
                await message.answer("🔥 Мотивация (тест):\n\n" + random.choice(texts), parse_mode=None)
                sent["motivation"] = True
            except Exception:
                pass



    await message.answer(
        "Итог теста напоминаний:\n"
        f"- принцип: {'ok' if sent['principle'] else 'нет'}\n"
        f"- мотивация: {'ok' if sent['motivation'] else 'нет'}",
        parse_mode=None,
    )






