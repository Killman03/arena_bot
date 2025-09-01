from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, Todo, NutritionReminder


def _weekday_str_to_int(name: str) -> int:
    """Конвертирует название дня недели в число (Monday=0, Sunday=6)"""
    mapping = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    return mapping[name]


async def create_nutrition_todos_for_user(session: AsyncSession, user_id: int) -> None:
    """
    Создает задачи для времени готовки и покупок пользователя.
    """
    try:
        # Получаем пользователя и его настройки питания
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        nutrition_reminder = (
            await session.execute(
                select(NutritionReminder).where(NutritionReminder.user_id == user_id)
            )
        ).scalar_one_or_none()
        
        if not nutrition_reminder or not nutrition_reminder.is_active:
            return
        
        # Получаем локальное время пользователя
        tz_name = user.timezone or settings.DEFAULT_TIMEZONE
        try:
            user_now = datetime.now(timezone.utc).astimezone(ZoneInfo(tz_name))
        except Exception:
            user_now = datetime.now(timezone.utc).astimezone(ZoneInfo(settings.DEFAULT_TIMEZONE))
        
        today = user_now.date()
        tasks_created = 0
        
        # Получаем дни готовки
        days = [d.strip().lower() for d in (nutrition_reminder.cooking_days or "").split(",") if d.strip()]
        cooking_weekdays = [_weekday_str_to_int(d) for d in days if d in {"sunday", "wednesday", "monday", "tuesday", "thursday", "friday", "saturday"}]
        
        # Проверяем, есть ли уже задачи на сегодня
        existing_todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == user_id,
                    Todo.due_date == today,
                    Todo.description.like("Задача питания:%")
                )
            )
        )
        existing_todos_list = existing_todos.scalars().all()
        existing_titles = [todo.title for todo in existing_todos_list]
        
        # Создаем задачи для времени готовки
        if user_now.weekday() in cooking_weekdays:
            cooking_task_title = f"👨‍🍳 Готовка в {nutrition_reminder.cooking_time}"
            if cooking_task_title not in existing_titles:
                todo = Todo(
                    user_id=user_id,
                    title=cooking_task_title,
                    description=f"Задача питания: Время готовки на сегодня. Время: {nutrition_reminder.cooking_time}",
                    due_date=today,
                    priority="high",  # Высокий приоритет для питания
                    is_daily=False,
                    is_completed=False,
                    reminder_time=nutrition_reminder.cooking_time,
                    is_reminder_active=True
                )
                session.add(todo)
                tasks_created += 1
                print(f"✅ Создана задача готовки для пользователя {user_id} на {today}")
        
        # Создаем задачи для времени покупок (за день до готовки)
        tomorrow = today + timedelta(days=1)
        tomorrow_weekday = (user_now.weekday() + 1) % 7
        
        if tomorrow_weekday in cooking_weekdays:
            shopping_task_title = f"🛒 Покупки в {nutrition_reminder.shopping_reminder_time}"
            if shopping_task_title not in existing_titles:
                todo = Todo(
                    user_id=user_id,
                    title=shopping_task_title,
                    description=f"Задача питания: Покупки для завтрашней готовки. Время: {nutrition_reminder.shopping_reminder_time}",
                    due_date=today,
                    priority="medium",  # Средний приоритет для покупок
                    is_daily=False,
                    is_completed=False,
                    reminder_time=nutrition_reminder.shopping_reminder_time,
                    is_reminder_active=True
                )
                session.add(todo)
                tasks_created += 1
                print(f"✅ Создана задача покупок для пользователя {user_id} на {today}")
        
        if tasks_created > 0:
            await session.commit()
            print(f"✅ Создано {tasks_created} задач питания для пользователя {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка при создании задач питания для пользователя {user_id}: {e}")


async def create_nutrition_todos_for_all_users(session: AsyncSession) -> None:
    """
    Создает задачи для времени готовки и покупок всех пользователей.
    """
    try:
        # Получаем всех пользователей
        users = (await session.execute(select(User))).scalars().all()
        
        for user in users:
            await create_nutrition_todos_for_user(session, user.id)
            
    except Exception as e:
        print(f"❌ Ошибка при создании задач питания для всех пользователей: {e}")


async def cleanup_old_nutrition_todos(session: AsyncSession, user_id: int) -> None:
    """
    Удаляет старые задачи питания (старше 3 дней).
    """
    try:
        today = date.today()
        three_days_ago = today - timedelta(days=3)
        
        # Удаляем старые задачи питания
        old_todos = await session.execute(
            select(Todo)
            .where(
                and_(
                    Todo.user_id == user_id,
                    Todo.due_date < three_days_ago,
                    Todo.description.like("Задача питания:%"),
                    Todo.is_completed == True  # Удаляем только выполненные
                )
            )
        )
        old_todos_list = old_todos.scalars().all()
        
        for todo in old_todos_list:
            await session.delete(todo)
        
        if old_todos_list:
            await session.commit()
            print(f"🗑️ Удалено {len(old_todos_list)} старых задач питания пользователя {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке старых задач питания: {e}")


async def get_nutrition_todos_for_user(session: AsyncSession, user_id: int) -> List[Todo]:
    """
    Получает все задачи питания пользователя.
    """
    try:
        result = await session.execute(
            select(Todo)
            .where(
                and_(
                    Todo.user_id == user_id,
                    Todo.description.like("Задача питания:%")
                )
            )
            .order_by(Todo.due_date.desc())
        )
        return result.scalars().all()
        
    except Exception as e:
        print(f"❌ Ошибка при получении задач питания: {e}")
        return []
