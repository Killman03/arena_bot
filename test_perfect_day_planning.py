#!/usr/bin/env python3
"""
Тест новой функциональности планирования идеального дня
с учетом времени напоминаний из todo-листа
"""

import asyncio
import sys
import os
from datetime import date, datetime
from sqlalchemy import select

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import session_scope
from app.db.models import User, Todo, Motivation, Goal, GoalStatus, GoalScope
from app.services.daily_reminders import generate_perfect_day_plan


async def test_perfect_day_planning():
    """Тестирует новую функциональность планирования идеального дня"""
    print("🧪 Тестирование новой функциональности планирования идеального дня")
    print("=" * 60)
    
    async with session_scope() as session:
        # Получаем первого пользователя для тестирования
        user = (await session.execute(select(User))).scalar_one_or_none()
        if not user:
            print("❌ Пользователи не найдены в базе данных")
            return
        
        print(f"👤 Тестируем для пользователя: {user.telegram_id}")
        
        # Создаем тестовые задачи с разными временами напоминаний
        test_todos = [
            {
                "title": "Утренняя тренировка",
                "description": "Кардио + силовая тренировка",
                "reminder_time": "06:00",
                "priority": "high"
            },
            {
                "title": "Работа над проектом",
                "description": "Разработка новой функции",
                "reminder_time": "09:00",
                "priority": "high"
            },
            {
                "title": "Обед",
                "description": "Правильное питание",
                "reminder_time": "13:00",
                "priority": "medium"
            },
            {
                "title": "Встреча с командой",
                "description": "Ежедневный стендап",
                "reminder_time": "15:00",
                "priority": "high"
            },
            {
                "title": "Чтение книги",
                "description": "Развитие и самообразование",
                "reminder_time": None,
                "priority": "medium"
            },
            {
                "title": "Вечерняя прогулка",
                "description": "Активный отдых",
                "reminder_time": None,
                "priority": "low"
            }
        ]
        
        print("\n📝 Создаем тестовые задачи...")
        
        # Удаляем старые тестовые задачи
        await session.execute(
            select(Todo).where(
                Todo.user_id == user.id,
                Todo.due_date == date.today()
            )
        )
        
        # Создаем новые тестовые задачи
        for todo_data in test_todos:
            todo = Todo(
                user_id=user.id,
                title=todo_data["title"],
                description=todo_data["description"],
                due_date=date.today(),
                priority=todo_data["priority"],
                is_daily=False,
                reminder_time=todo_data["reminder_time"],
                is_reminder_active=bool(todo_data["reminder_time"])
            )
            session.add(todo)
        
        await session.commit()
        print("✅ Тестовые задачи созданы")
        
        # Проверяем созданные задачи
        todos = (await session.execute(
            select(Todo).where(
                Todo.user_id == user.id,
                Todo.due_date == date.today()
            ).order_by(Todo.reminder_time.asc().nullslast(), Todo.priority.desc())
        )).scalars().all()
        
        print("\n📋 Созданные задачи:")
        for todo in todos:
            time_info = f" ⏰{todo.reminder_time}" if todo.reminder_time else ""
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(todo.priority, "⚪")
            print(f"  • {priority_emoji} {todo.title}{time_info} - {todo.description}")
        
        # Генерируем план идеального дня
        print("\n⚔️ Генерируем план идеального дня...")
        plan = await generate_perfect_day_plan(user.id, session)
        
        print("\n" + "=" * 60)
        print("📋 ПЛАН ИДЕАЛЬНОГО ДНЯ:")
        print("=" * 60)
        print(plan)
        print("=" * 60)
        
        # Анализируем план
        print("\n🔍 Анализ плана:")
        
        # Проверяем, содержит ли план упоминания времени
        time_mentions = []
        for line in plan.split('\n'):
            if ':' in line and any(char.isdigit() for char in line):
                time_mentions.append(line.strip())
        
        if time_mentions:
            print("✅ План содержит временные рамки:")
            for mention in time_mentions[:5]:  # Показываем первые 5
                print(f"  • {mention}")
        else:
            print("⚠️ План не содержит явных временных рамок")
        
        # Проверяем упоминания задач
        task_mentions = []
        for todo in todos:
            if todo.title.lower() in plan.lower():
                task_mentions.append(todo.title)
        
        if task_mentions:
            print(f"✅ План учитывает {len(task_mentions)} из {len(todos)} задач:")
            for task in task_mentions:
                print(f"  • {task}")
        else:
            print("⚠️ План не содержит упоминаний конкретных задач")
        
        print("\n✅ Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(test_perfect_day_planning())
