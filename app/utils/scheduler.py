from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.reminders import send_daily_principle, send_daily_motivation
from sqlalchemy import select
from app.db.models import User, Habit, HabitLog, Challenge


class AppScheduler:
    """Wrapper around APScheduler to register periodic jobs."""

    def __init__(self, bot: Bot, session_factory: callable[[], AsyncSession]):
        self.scheduler = AsyncIOScheduler(timezone=settings.default_timezone)
        self.bot = bot
        self.session_factory = session_factory

    def start(self) -> None:
        hour = settings.daily_principle_reminder_hour
        self.scheduler.add_job(self._daily_principle_job, CronTrigger(hour=hour, minute=0))
        # Мотивация в 8 утра
        self.scheduler.add_job(self._daily_motivation_job, CronTrigger(hour=8, minute=0))
        # персональные напоминания по привычкам: проверка каждые 60 секунд
        self.scheduler.add_job(self._habit_reminders_job, IntervalTrigger(seconds=60))
        self.scheduler.start()

    async def _daily_principle_job(self) -> None:
        async with self.session_factory() as session:  # type: ignore[misc]
            await send_daily_principle(self.bot, session)

    async def _daily_motivation_job(self) -> None:
        async with self.session_factory() as session:  # type: ignore[misc]
            await send_daily_motivation(self.bot, session)

    async def _habit_reminders_job(self) -> None:
        """Check per-user habit reminder times and send nudges if within a small window."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

        # Use UTC for base moment and convert per-user timezone for comparisons
        now_utc = datetime.now(timezone.utc)
        async with self.session_factory() as session:  # type: ignore[misc]
            users = (await session.execute(select(User))).scalars().all()

            # Habit reminders per user timezone
            for u in users:
                user_tz_name = u.timezone or settings.default_timezone
                try:
                    user_now = now_utc.astimezone(ZoneInfo(user_tz_name))
                except Exception:
                    user_now = now_utc.astimezone(ZoneInfo(settings.default_timezone))
                user_hhmm = user_now.strftime("%H:%M")

                prefs = u.notification_preferences or {}
                habit_times = prefs.get("habit_times", {})
                for habit_name, time_str in habit_times.items():
                    if time_str == user_hhmm:
                        try:
                            await self.bot.send_message(u.telegram_id, f"Напоминание: {habit_name} ({user_tz_name})")
                        except Exception:
                            continue

            # Challenge reminders per owner timezone (daily except masked days)
            ch_list = (await session.execute(select(Challenge))).scalars().all()
            for ch in ch_list:
                if not ch.is_active:
                    continue
                owner = (await session.execute(select(User).where(User.id == ch.user_id))).scalar_one_or_none()
                if not owner:
                    continue
                owner_tz = owner.timezone or settings.default_timezone
                try:
                    owner_now = now_utc.astimezone(ZoneInfo(owner_tz))
                except Exception:
                    owner_now = now_utc.astimezone(ZoneInfo(settings.default_timezone))
                weekday = owner_now.weekday()  # Mon=0 .. Sun=6
                if len(ch.days_mask) == 7 and ch.days_mask[weekday] != "1":
                    continue
                if ch.time_str == owner_now.strftime("%H:%M"):
                    try:
                        await self.bot.send_message(owner.telegram_id, f"🏆 Напоминание по челленджу: {ch.title} ({owner_tz})")
                    except Exception:
                        continue


