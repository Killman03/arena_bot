from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Set

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.daily_reminders import send_daily_principle, send_daily_motivation
from app.services.nutrition_reminders import (
    send_cooking_day_reminders,
    send_shopping_day_reminders,
)
from app.services.health_reminders import send_health_daily_prompt
from app.services.goal_reminders import send_goal_reminders
from app.services.todo_reminders import send_todo_reminders
from app.services.finance_reminders import send_finance_reminders, send_finance_reminders_for_user
from app.services.finance_todo_manager import create_todos_for_all_users
from app.services.nutrition_todo_manager import create_nutrition_todos_for_all_users
from app.utils.timezone_utils import is_time_to_send_reminder, get_user_time_info

from sqlalchemy import select
from app.db.models import User


class AppScheduler:
    """Wrapper around APScheduler to register periodic jobs with user timezone support."""

    def __init__(self, bot: Bot, session_factory: callable[[], AsyncSession]):
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.bot = bot
        self.session_factory = session_factory
        # Отслеживание отправленных напоминаний: {user_id: {reminder_type: last_sent_date}}
        self.sent_reminders: Dict[int, Dict[str, str]] = {}

    def _get_reminder_key(self, user_id: int, reminder_type: str) -> str:
        """Генерирует ключ для отслеживания напоминания"""
        return f"{user_id}_{reminder_type}"

    def _is_reminder_sent_today(self, user_id: int, reminder_type: str) -> bool:
        """Проверяет, было ли уже отправлено напоминание сегодня"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = self._get_reminder_key(user_id, reminder_type)
        return self.sent_reminders.get(key) == today

    def _mark_reminder_sent(self, user_id: int, reminder_type: str) -> None:
        """Отмечает напоминание как отправленное"""
        today = datetime.now().strftime("%Y-%m-%d")
        key = self._get_reminder_key(user_id, reminder_type)
        self.sent_reminders[key] = today

    def start(self) -> None:
        """Запускает планировщик с поддержкой часовых поясов пользователей."""
        print("🚀 Запуск AppScheduler с поддержкой часовых поясов пользователей")
        
        # Все задачи выполняются каждую минуту для проверки времени пользователей
        # Это позволяет учитывать индивидуальные часовые пояса
        self.scheduler.add_job(self._daily_principle_job, IntervalTrigger(minutes=1))
        self.scheduler.add_job(self._daily_motivation_job, IntervalTrigger(minutes=1))
        
        # Напоминания по готовке и спискам покупок
        self.scheduler.add_job(self._nutrition_cooking_job, IntervalTrigger(minutes=1))
        self.scheduler.add_job(self._nutrition_shopping_job, IntervalTrigger(minutes=1))
        
        # Здоровье: ежедневные напоминания о вводе показателей
        self.scheduler.add_job(self._health_daily_prompt_job, IntervalTrigger(minutes=1))
        
        # Напоминания по целям
        self.scheduler.add_job(self._goal_reminders_job, IntervalTrigger(minutes=1))
        
        # Напоминания по to-do задачам
        self.scheduler.add_job(self._todo_reminders_job, IntervalTrigger(minutes=1))
        
        # Финансовые напоминания
        self.scheduler.add_job(self._finance_reminders_job, IntervalTrigger(minutes=1))
        
        # Создание задач To-Do для финансовых обязательств
        self.scheduler.add_job(self._finance_todo_creation_job, IntervalTrigger(minutes=1))
        
        # To-Do: вечерние напоминания о составлении списка на завтра
        self.scheduler.add_job(self._todo_evening_reminder_job, IntervalTrigger(minutes=1))
        
        # To-Do: сброс ежедневных задач каждое утро
        self.scheduler.add_job(self._daily_tasks_reset_job, IntervalTrigger(minutes=1))
        
        self.scheduler.start()
        print("✅ AppScheduler запущен успешно")

    async def _daily_principle_job(self) -> None:
        """Отправка принципов арены с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                print(f"🔄 Проверка ежедневных принципов для {len(users)} пользователей")
                
                for user in users:
                    try:
                        # Проверяем настройки уведомлений
                        prefs = user.notification_preferences or {}
                        if not prefs.get("daily_principle", True):
                            continue
                        
                        # Проверяем, было ли уже отправлено напоминание сегодня
                        if self._is_reminder_sent_today(user.id, "daily_principle"):
                            continue
                        
                        # Проверяем, пора ли отправлять напоминание (7:00 по местному времени пользователя)
                        if is_time_to_send_reminder(user.timezone, 7):
                            time_info = get_user_time_info(user.timezone)
                            print(f"🕐 Отправляем ежедневный принцип пользователю {user.id} "
                                  f"в {time_info['user_local_time'].strftime('%H:%M')} "
                                  f"({time_info['timezone']})")
                            
                            await send_daily_principle(self.bot, session, user_id=user.id)
                            # Отмечаем как отправленное
                            self._mark_reminder_sent(user.id, "daily_principle")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при отправке принципа пользователю {user.id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _daily_principle_job: {e}")

    async def _daily_motivation_job(self) -> None:
        """Отправка мотивации с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                
                for user in users:
                    try:
                        # Проверяем настройки уведомлений
                        prefs = user.notification_preferences or {}
                        if not prefs.get("daily_motivation", True):
                            continue
                        
                        # Проверяем, было ли уже отправлено напоминание сегодня
                        if self._is_reminder_sent_today(user.id, "daily_motivation"):
                            continue
                        
                        # Проверяем, пора ли отправлять напоминание (8:00 по местному времени пользователя)
                        if is_time_to_send_reminder(user.timezone, 8):
                            time_info = get_user_time_info(user.timezone)
                            print(f"🕐 Отправляем мотивацию пользователю {user.id} "
                                  f"в {time_info['user_local_time'].strftime('%H:%M')} "
                                  f"({time_info['timezone']})")
                            
                            await send_daily_motivation(self.bot, session, user_id=user.id)
                            # Отмечаем как отправленное
                            self._mark_reminder_sent(user.id, "daily_motivation")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при отправке мотивации пользователю {user.id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _daily_motivation_job: {e}")

    async def _nutrition_cooking_job(self) -> None:
        """Напоминания о готовке с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                
                for user in users:
                    try:
                        # Проверяем настройки уведомлений
                        prefs = user.notification_preferences or {}
                        if not prefs.get("nutrition_cooking", True):
                            continue
                        
                        # Проверяем, было ли уже отправлено напоминание сегодня
                        if self._is_reminder_sent_today(user.id, "nutrition_cooking"):
                            continue
                        
                        # Проверяем, пора ли отправлять напоминание (18:00 по местному времени пользователя)
                        if is_time_to_send_reminder(user.timezone, 18):
                            time_info = get_user_time_info(user.timezone)
                            print(f"🕐 Отправляем напоминание о готовке пользователю {user.id} "
                                  f"в {time_info['user_local_time'].strftime('%H:%M')} "
                                  f"({time_info['timezone']})")
                            
                            await send_cooking_day_reminders(self.bot, session, user_id=user.id)
                            
                            # Создаем задачи питания для этого пользователя
                            await create_nutrition_todos_for_all_users(session)
                            
                            # Отмечаем как отправленное
                            self._mark_reminder_sent(user.id, "nutrition_cooking")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при отправке напоминания о готовке пользователю {user.id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _nutrition_cooking_job: {e}")

    async def _nutrition_shopping_job(self) -> None:
        """Напоминания о покупках с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                
                for user in users:
                    try:
                        # Проверяем настройки уведомлений
                        prefs = user.notification_preferences or {}
                        if not prefs.get("nutrition_shopping", True):
                            continue
                        
                        # Проверяем, было ли уже отправлено напоминание сегодня
                        if self._is_reminder_sent_today(user.id, "nutrition_shopping"):
                            continue
                        
                        # Проверяем, пора ли отправлять напоминание (16:00 по местному времени пользователя)
                        if is_time_to_send_reminder(user.timezone, 16):
                            time_info = get_user_time_info(user.timezone)
                            print(f"🕐 Отправляем напоминание о покупках пользователю {user.id} "
                                  f"в {time_info['user_local_time'].strftime('%H:%M')} "
                                  f"({time_info['timezone']})")
                            
                            await send_shopping_day_reminders(self.bot, session, user_id=user.id)
                            
                            # Создаем задачи питания для этого пользователя
                            await create_nutrition_todos_for_all_users(session)
                            
                            # Отмечаем как отправленное
                            self._mark_reminder_sent(user.id, "nutrition_shopping")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при отправке напоминания о покупках пользователю {user.id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _nutrition_shopping_job: {e}")

    async def _health_daily_prompt_job(self) -> None:
        """Ежедневные напоминания о здоровье с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                
                for user in users:
                    try:
                        # Проверяем настройки уведомлений
                        prefs = user.notification_preferences or {}
                        if not prefs.get("health_daily", True):
                            continue
                        
                        # Проверяем, было ли уже отправлено напоминание сегодня
                        if self._is_reminder_sent_today(user.id, "health_daily"):
                            continue
                        
                        # Проверяем, пора ли отправлять напоминание (9:00 по местному времени пользователя)
                        if is_time_to_send_reminder(user.timezone, 9):
                            time_info = get_user_time_info(user.timezone)
                            print(f"🕐 Отправляем напоминание о здоровье пользователю {user.id} "
                                  f"в {time_info['user_local_time'].strftime('%H:%M')} "
                                  f"({time_info['timezone']})")
                            
                            await send_health_daily_prompt(self.bot, session, user_id=user.id)
                            # Отмечаем как отправленное
                            self._mark_reminder_sent(user.id, "health_daily")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при отправке напоминания о здоровье пользователю {user.id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _health_daily_prompt_job: {e}")

    async def _goal_reminders_job(self) -> None:
        """Отправка напоминаний по целям с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Отправляем напоминания по целям
                await send_goal_reminders(session, self.bot)
                
            except Exception as e:
                print(f"❌ Ошибка в _goal_reminders_job: {e}")

    async def _todo_reminders_job(self) -> None:
        """Отправка напоминаний по to-do задачам с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Отправляем напоминания по to-do задачам
                await send_todo_reminders(session, self.bot)
                
            except Exception as e:
                print(f"❌ Ошибка в _todo_reminders_job: {e}")

    async def _finance_reminders_job(self) -> None:
        """Отправка финансовых напоминаний с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                
                for user in users:
                    try:
                        # Проверяем настройки уведомлений
                        prefs = user.notification_preferences or {}
                        if not prefs.get("finance_reminders", True):
                            continue
                        
                        # Проверяем, было ли уже отправлено напоминание сегодня
                        if self._is_reminder_sent_today(user.id, "finance_reminders"):
                            continue
                        
                        # Отправляем финансовые напоминания конкретному пользователю
                        await send_finance_reminders_for_user(session, user.id, self.bot)
                            
                    except Exception as e:
                        print(f"❌ Ошибка при отправке финансового напоминания пользователю {user.telegram_id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _finance_reminders_job: {e}")

    async def _finance_todo_creation_job(self) -> None:
        """Создание задач To-Do для финансовых обязательств с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                
                for user in users:
                    try:
                        # Проверяем настройки уведомлений
                        prefs = user.notification_preferences or {}
                        if not prefs.get("finance_todo_creation", True):
                            continue
                        
                        # Проверяем, было ли уже создано задач сегодня
                        if self._is_reminder_sent_today(user.id, "finance_todo_creation"):
                            continue
                        
                        # Проверяем, пора ли создавать задачи (6:00 по местному времени пользователя)
                        if is_time_to_send_reminder(user.timezone, 6):
                            time_info = get_user_time_info(user.timezone)
                            print(f"🕐 Создаем задачи To-Do для финансовых обязательств пользователю {user.id} "
                                  f"в {time_info['user_local_time'].strftime('%H:%M')} "
                                  f"({time_info['timezone']})")
                            
                            from app.services.finance_todo_manager import create_todo_for_financial_obligations
                            await create_todo_for_financial_obligations(session, user.id)
                            
                            # Отмечаем как выполненное
                            self._mark_reminder_sent(user.id, "finance_todo_creation")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при создании задач To-Do для финансовых обязательств пользователя {user.id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _finance_todo_creation_job: {e}")

    async def _todo_evening_reminder_job(self) -> None:
        """Вечернее напоминание о составлении To-Do списка с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                
                for user in users:
                    try:
                        # Проверяем настройки уведомлений
                        prefs = user.notification_preferences or {}
                        if not prefs.get("todo_evening", True):
                            continue
                        
                        # Проверяем, было ли уже отправлено напоминание сегодня
                        if self._is_reminder_sent_today(user.id, "todo_evening"):
                            continue
                        
                        # Проверяем, пора ли отправлять напоминание (20:00 по местному времени пользователя)
                        if is_time_to_send_reminder(user.timezone, 20):
                            time_info = get_user_time_info(user.timezone)
                            print(f"🕐 Отправляем вечернее напоминание пользователю {user.id} "
                                  f"в {time_info['user_local_time'].strftime('%H:%M')} "
                                  f"({time_info['timezone']})")
                            
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
                            
                            # Отмечаем как отправленное
                            self._mark_reminder_sent(user.id, "todo_evening")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при отправке вечернего напоминания пользователю {user.telegram_id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _todo_evening_reminder_job: {e}")

    async def _daily_tasks_reset_job(self) -> None:
        """Сброс ежедневных задач с учетом часового пояса пользователя"""
        async with self.session_factory() as session:  # type: ignore[misc]
            try:
                # Получаем всех пользователей
                users = (await session.execute(select(User))).scalars().all()
                
                for user in users:
                    try:
                        # Проверяем, было ли уже выполнено сброс сегодня
                        if self._is_reminder_sent_today(user.id, "daily_tasks_reset"):
                            continue
                        
                        # Проверяем, пора ли сбрасывать задачи (6:00 по местному времени пользователя)
                        if is_time_to_send_reminder(user.timezone, 6):
                            time_info = get_user_time_info(user.timezone)
                            print(f"🕐 Сбрасываем ежедневные задачи пользователю {user.id} "
                                  f"в {time_info['user_local_time'].strftime('%H:%M')} "
                                  f"({time_info['timezone']})")
                            
                            from app.services.daily_tasks_manager import reset_daily_tasks
                            await reset_daily_tasks(session, user.id)
                            
                            # Создаем задачи питания
                            await create_nutrition_todos_for_all_users(session)
                            
                            # Отмечаем как выполненное
                            self._mark_reminder_sent(user.id, "daily_tasks_reset")
                            
                    except Exception as e:
                        print(f"❌ Ошибка при сбросе ежедневных задач для пользователя {user.id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в _daily_tasks_reset_job: {e}")

    def stop(self) -> None:
        """Останавливает планировщик"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("🛑 AppScheduler остановлен")



