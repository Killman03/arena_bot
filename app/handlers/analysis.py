from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.db.session import session_scope
from app.db.models import User, Goal, Habit, HabitLog, PomodoroSession

router = Router()


@router.message(Command("analysis"))
async def analysis_handler(message: types.Message) -> None:
    """Show user's progress analysis"""
    user = message.from_user
    if not user:
        return

    async with session_scope() as session:
        # Get user from database
        db_user = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = db_user.scalar_one_or_none()
        
        if not db_user:
            await message.answer("Пользователь не найден. Сначала зарегистрируйтесь с помощью /start")
            return

        # Get basic stats
        goals_count = await session.execute(
            select(func.count(Goal.id)).where(Goal.user_id == db_user.id)
        )
        goals_count = goals_count.scalar()

        active_habits = await session.execute(
            select(func.count(Habit.id)).where(
                Habit.user_id == db_user.id,
                Habit.is_active == True
            )
        )
        active_habits = active_habits.scalar()

        # Get habit completion rate for last 7 days
        week_ago = datetime.now() - timedelta(days=7)
        habit_logs = await session.execute(
            select(HabitLog).join(Habit).where(
                Habit.user_id == db_user.id,
                HabitLog.completed_at >= week_ago
            )
        )
        habit_logs = habit_logs.scalars().all()

        completion_rate = 0
        if active_habits > 0:
            total_possible = active_habits * 7  # 7 days
            actual_completions = len(habit_logs)
            completion_rate = (actual_completions / total_possible) * 100 if total_possible > 0 else 0

        # Get productivity stats
        pomodoro_sessions = await session.execute(
            select(func.count(PomodoroSession.id)).where(
                PomodoroSession.user_id == db_user.id,
                PomodoroSession.completed_at >= week_ago
            )
        )
        pomodoro_sessions = pomodoro_sessions.scalar()

        analysis_text = f"""
📊 **Анализ вашего прогресса**

🎯 **Цели**: {goals_count} активных целей
✅ **Привычки**: {active_habits} активных привычек
📈 **Выполнение привычек за неделю**: {completion_rate:.1f}%
🍅 **Помодоро сессии за неделю**: {pomodoro_sessions}

💡 **Рекомендации**:
"""
        
        if completion_rate < 50:
            analysis_text += "• Попробуйте упростить привычки или уменьшить их количество\n"
        if pomodoro_sessions < 5:
            analysis_text += "• Увеличьте количество рабочих сессий для лучшей продуктивности\n"
        if goals_count == 0:
            analysis_text += "• Поставьте хотя бы одну цель для направления развития\n"
        
        if completion_rate >= 80 and pomodoro_sessions >= 10:
            analysis_text += "• Отличная работа! Вы на правильном пути! 🚀\n"

        await message.answer(analysis_text)


@router.message(Command("stats"))
async def stats_handler(message: types.Message) -> None:
    """Show detailed statistics"""
    user = message.from_user
    if not user:
        return

    async with session_scope() as session:
        db_user = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = db_user.scalar_one_or_none()
        
        if not db_user:
            await message.answer("Пользователь не найден. Сначала зарегистрируйтесь с помощью /start")
            return

        # Get user creation date
        days_registered = (datetime.now() - db_user.created_at.replace(tzinfo=None)).days

        stats_text = f"""
📈 **Подробная статистика**

👤 **Пользователь**: {db_user.first_name or 'Неизвестно'}
📅 **В системе**: {days_registered} дней
🆔 **Telegram ID**: {db_user.telegram_id}

Используйте /analysis для анализа прогресса
"""
        
        await message.answer(stats_text)
