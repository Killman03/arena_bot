from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.reminders import send_daily_principle, send_daily_motivation
from app.services.nutrition_reminders import (
    send_cooking_day_reminders,
    send_shopping_day_reminders,
)
from app.services.health_reminders import send_health_daily_prompt, sync_google_fit_data
from app.services.challenge_cleanup import cleanup_expired_challenges
from sqlalchemy import select
from app.db.models import User, Challenge


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

        # Напоминания по готовке и спискам покупок (ежечасная проверка времени пользователей)
        self.scheduler.add_job(self._nutrition_cooking_job, IntervalTrigger(minutes=1))
        self.scheduler.add_job(self._nutrition_shopping_job, IntervalTrigger(minutes=1))
        # Здоровье: ежедневные напоминания о вводе показателей
        self.scheduler.add_job(self._health_daily_prompt_job, IntervalTrigger(minutes=1))
        # Google Fit: автоматическая синхронизация данных
        self.scheduler.add_job(self._google_fit_sync_job, IntervalTrigger(hours=6))  # Каждые 6 часов
        
        # Очистка истекших челленджей (ежедневно в 00:01)
        self.scheduler.add_job(self._challenge_cleanup_job, CronTrigger(hour=0, minute=1))
        
        # To-Do: вечерние напоминания о составлении списка на завтра (в 20:00)
        self.scheduler.add_job(self._todo_evening_reminder_job, CronTrigger(hour=20, minute=0))
        
        self.scheduler.start()

    async def _daily_principle_job(self) -> None:
        async with self.session_factory() as session:  # type: ignore[misc]
            await send_daily_principle(self.bot, session)

    async def _daily_motivation_job(self) -> None:
        async with self.session_factory() as session:  # type: ignore[misc]
            await send_daily_motivation(self.bot, session)



    async def _nutrition_cooking_job(self) -> None:
        async with self.session_factory() as session:  # type: ignore[misc]
            await send_cooking_day_reminders(self.bot, session)

    async def _nutrition_shopping_job(self) -> None:
        async with self.session_factory() as session:  # type: ignore[misc]
            await send_shopping_day_reminders(self.bot, session)

    async def _health_daily_prompt_job(self) -> None:
        async with self.session_factory() as session:  # type: ignore[misc]
            await send_health_daily_prompt(self.bot, session)

    async def _google_fit_sync_job(self) -> None:
        async with self.session_factory() as session:  # type: ignore[misc]
            await sync_google_fit_data(self.bot, session)

    async def _todo_evening_reminder_job(self) -> None:
        """Вечернее напоминание о составлении To-Do списка на завтра"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                users = await session.execute(select(User))
                users_list = users.scalars().all()
                
                for user in users_list:
                    try:
                        # Отправляем напоминание с кнопками для быстрого добавления задач
                        from app.keyboards.common import todo_daily_reminder_keyboard
                        
                        await self.bot.send_message(
                            user.telegram_id,
                            "🌙 <b>Вечернее напоминание</b>\n\n"
                            "Не забудьте составить список дел на завтра! 📝\n\n"
                            "Это поможет вам лучше планировать день и быть более продуктивным. ✨",
                            reply_markup=todo_daily_reminder_keyboard(),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"Ошибка при отправке вечернего напоминания пользователю {user.telegram_id}: {e}")
                        
            except Exception as e:
                print(f"Ошибка в _todo_evening_reminder_job: {e}")

    async def _challenge_cleanup_job(self) -> None:
        """Очистка истекших челленджей"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                await cleanup_expired_challenges(session, self.bot)
            except Exception as e:
                print(f"Ошибка в _challenge_cleanup_job: {e}")


