from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, HealthDailyReminder


async def send_health_daily_prompt(bot: Bot, session: AsyncSession) -> None:
    now_utc = datetime.now(timezone.utc)
    users = (await session.execute(select(User))).scalars().all()
    for u in users:
        tz = u.timezone or settings.DEFAULT_TIMEZONE
        try:
            user_now = now_utc.astimezone(ZoneInfo(tz))
        except Exception:
            user_now = now_utc.astimezone(ZoneInfo(settings.DEFAULT_TIMEZONE))
        rec = (
            await session.execute(select(HealthDailyReminder).where(HealthDailyReminder.user_id == u.id))
        ).scalar_one_or_none()
        if not rec or not rec.is_active:
            continue
        if user_now.strftime("%H:%M") != rec.time_str:
            continue
        try:
            await bot.send_message(
                u.telegram_id,
                "🔔 Пора записать показатели здоровья: шаги, сон, вес и др. Зайдите в '🩺 Здоровье' → '📈 Трекинг показателей'.",
            )
        except Exception:
            continue





