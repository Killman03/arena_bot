454from __future__ import annotations

from datetime import date

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.models import Habit, HabitLog, Periodicity, User
from app.db.session import session_scope
from app.services.llm import deepseek_complete

router = Router()


DEFAULT_HABITS = [
    ("Бег", Periodicity.week, 3.0),
    ("Математика", Periodicity.day, 3.0),
    ("Чтение", Periodicity.week, 7.0),
    ("Ранний подъем", Periodicity.day, 1.0),
    ("Отжимания", Periodicity.day, 1.0),
    ("Йога", Periodicity.day, 1.0),
    ("Трейдинг", Periodicity.day, 1.5),
]


@router.message(Command("habits_init"))
async def init_habits(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        for name, periodicity, target in DEFAULT_HABITS:
            exists = (
                await session.execute(select(Habit).where(Habit.user_id == db_user.id, Habit.name == name))
            ).scalar_one_or_none()
            if not exists:
                session.add(
                    Habit(user_id=db_user.id, name=name, periodicity=periodicity, target_value=target, start_date=date.today())
                )
    await message.answer("Базовые привычки созданы ✅")


@router.message(Command("habit"))
async def log_habit(message: types.Message) -> None:
    """Quick log: /habit Название 1.0 [YYYY-MM-DD]."""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/habit", "", 1).strip()
    if not payload:
        await message.answer("Использование: /habit Название 1.0 [YYYY-MM-DD]")
        return
    parts = payload.split()
    try:
        value = float(parts[-1])
        name = " ".join(parts[:-1])
        log_date = date.today()
    except ValueError:
        # assume last is date
        value = float(parts[-2])
        name = " ".join(parts[:-2])
        log_date = date.fromisoformat(parts[-1])

    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        habit = (
            await session.execute(select(Habit).where(Habit.user_id == db_user.id, Habit.name.ilike(name)))
        ).scalar_one_or_none()
        if not habit:
            await message.answer("Привычка не найдена. Создайте ее сначала.")
            return
        session.add(HabitLog(habit_id=habit.id, date=log_date, value=value))
    # AI: короткая обратная связь
    status_msg = await message.answer("⏳ Генерирую обратную связь...")
    try:
        feedback = await deepseek_complete(
            f"Пользователь логирует привычку '{name}' на значение {value}. Дай краткую мотивационную обратную связь одним абзацем.",
            system="Ты коуч-мотиватор",
        )
        await status_msg.edit_text("Записано ✅\n" + feedback)
    except Exception:
        await status_msg.edit_text("Записано ✅")


@router.message(Command("remind_habit"))
async def remind_habit(message: types.Message) -> None:
    """Создать персональное напоминание по привычке: /remind_habit Название HH:MM"""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/remind_habit", "", 1).strip()
    if not payload or " " not in payload:
        await message.answer("Пример: /remind_habit Бег 07:00")
        return
    name, t = payload.rsplit(" ", 1)
    # Сохраним в preferences пользователя маску времени для упрощенного планировщика
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        prefs = dict(db_user.notification_preferences or {})
        habit_times = dict(prefs.get("habit_times", {}))
        habit_times[name] = t
        prefs["habit_times"] = habit_times
        db_user.notification_preferences = prefs
    await message.answer(f"Напоминание по '{name}' установлено на {t} ✅\nУчти: используется часовой пояс {settings.default_timezone}")


