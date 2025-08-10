from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Iterable

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
# Email reminders removed per new requirements
from app.db.models import User
from app.db.models.motivation import Motivation


LAWS_OF_ARENA: list[str] = [
    "Мне нужен только один идеальный день",
    "Мужчина делает то что должен, несмотря на то, как он себя чувствует",
    "Ясность только в действие",
    "Мужчина не был создан для комфорта",
    "Каждая сложная ситуация это тест на силу характера, которую я разношу, чтобы стать сильнее",
    "Я не жду идеального времени. Я делаю все, что может быть сделано сегодня",
    "Я обречен быть рабом привычек, поэтому я выбираю быть в рабстве привычек, которые меня строят",
    "За все в жизни ответственен только я. Если я хочу что-нибудь изменить я полагаюсь только на свои действия",
    "Время всегда есть до рассвета",
    "Когда вдохновение работать заканчивается, начинается настоящая работа",
    "Процесс важнее цели. Победители держат фокус на ежедневном процессе",
]


async def send_daily_principle(bot: Bot, session: AsyncSession) -> None:
    """Send a random arena principle to all users who opted-in for reminders."""
    users = await _get_all_users(session)
    if not users:
        return
    import random

    principle = random.choice(LAWS_OF_ARENA)
    for user in users:
        prefs = user.notification_preferences or {}
        if prefs.get("daily_principle", True):
            try:
                await bot.send_message(user.telegram_id, f"Дневной принцип арены:\n\n{principle}")
            except Exception:  # pragma: no cover
                continue
        # no email delivery


async def send_daily_motivation(bot: Bot, session: AsyncSession) -> None:
    """Send one of user's motivation texts (vision/mission/values/year goal)."""
    users = await _get_all_users(session)
    for user in users:
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == user.id))
        ).scalar_one_or_none()
        if not mot:
            continue
        texts = [t for t in [mot.main_year_goal, mot.vision, mot.mission, mot.values] if t]
        if not texts:
            continue
        import random

        text = random.choice(texts)
        try:
            await bot.send_message(user.telegram_id, f"🔥 Мотивация дня:\n\n{text}")
        except Exception:
            continue


async def _get_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User))
    return list(result.scalars().all())


