from __future__ import annotations

from datetime import datetime
import random

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User
from app.db.models.motivation import Motivation
from app.db.models.challenge import Challenge
from app.services.reminders import LAWS_OF_ARENA

router = Router()


@router.message(Command("test_reminders"))
async def test_reminders(message: types.Message) -> None:
    """Manually test reminder deliveries for the current user."""
    user = message.from_user
    if not user:
        return

    sent = {"principle": False, "motivation": False, "habits": 0, "challenges": 0}

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

        # Habit reminders (simulate all configured)
        prefs = db_user.notification_preferences or {}
        habit_times = prefs.get("habit_times", {})
        for habit_name in habit_times.keys():
            try:
                await message.answer(f"Напоминание по привычке (тест): {habit_name}")
                sent["habits"] += 1
            except Exception:
                continue

        # Challenge reminders (simulate for today if allowed by days_mask and active)
        weekday = datetime.now().weekday()  # Mon=0 .. Sun=6
        ch_list = (
            await session.execute(select(Challenge).where(Challenge.user_id == db_user.id))
        ).scalars().all()
        for ch in ch_list:
            if not ch.is_active:
                continue
            if len(ch.days_mask) == 7 and ch.days_mask[weekday] != "1":
                continue
            try:
                await message.answer(f"🏆 Напоминание по челленджу (тест): {ch.title}")
                sent["challenges"] += 1
            except Exception:
                continue

    await message.answer(
        "Итог теста напоминаний:\n"
        f"- принцип: {'ok' if sent['principle'] else 'нет'}\n"
        f"- мотивация: {'ok' if sent['motivation'] else 'нет'}\n"
        f"- привычки: {sent['habits']}\n"
        f"- челленджи: {sent['challenges']}",
        parse_mode=None,
    )



