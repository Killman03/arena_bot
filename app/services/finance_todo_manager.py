from __future__ import annotations

from datetime import date, datetime
from typing import List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Creditor, Debtor, Todo, User


async def create_todo_for_financial_obligations(session: AsyncSession, user_id: int) -> None:
    """
    Создает задачи в To-Do для финансовых обязательств, срок которых наступил сегодня.
    """
    try:
        today = date.today()
        
        # Получаем кредиторов с сегодняшней датой
        creditors_due_today = await session.execute(
            select(Creditor)
            .where(
                and_(
                    Creditor.user_id == user_id,
                    Creditor.is_active == True,
                    Creditor.due_date == today
                )
            )
        )
        creditors_list = creditors_due_today.scalars().all()
        
        # Получаем должников с сегодняшней датой
        debtors_due_today = await session.execute(
            select(Debtor)
            .where(
                and_(
                    Debtor.user_id == user_id,
                    Debtor.is_active == True,
                    Debtor.due_date == today
                )
            )
        )
        debtors_list = debtors_due_today.scalars().all()
        
        # Проверяем, не созданы ли уже задачи для этих обязательств сегодня
        existing_todos = await session.execute(
            select(Todo)
            .where(
                and_(
                    Todo.user_id == user_id,
                    Todo.due_date == today,
                    Todo.description.like("Финансовое обязательство:%")
                )
            )
        )
        existing_todos_list = existing_todos.scalars().all()
        
        # Создаем множество уже созданных задач для избежания дублирования
        existing_task_ids = set()
        for todo in existing_todos_list:
            if todo.description and "Финансовое обязательство:" in todo.description:
                # Извлекаем ID из описания
                try:
                    task_id = int(todo.description.split("ID:")[1].split()[0])
                    existing_task_ids.add(task_id)
                except (IndexError, ValueError):
                    continue
        
        tasks_created = 0
        
        # Создаем задачи для кредиторов
        for creditor in creditors_list:
            if creditor.id not in existing_task_ids:
                todo = Todo(
                    user_id=user_id,
                    title=f"Получить долг от {creditor.name}",
                    description=f"Финансовое обязательство: Кредитор ID:{creditor.id} - {creditor.name} должен {float(creditor.amount):,.2f} ₽. Описание: {creditor.description or 'Не указано'}",
                    due_date=today,
                    priority="high",  # Высокий приоритет для финансовых обязательств
                    is_daily=False,
                    is_completed=False
                )
                session.add(todo)
                tasks_created += 1
        
        # Создаем задачи для должников
        for debtor in debtors_list:
            if debtor.id not in existing_task_ids:
                todo = Todo(
                    user_id=user_id,
                    title=f"Отдать долг {debtor.name}",
                    description=f"Финансовое обязательство: Должник ID:{debtor.id} - вы должны {debtor.name} {float(debtor.amount):,.2f} ₽. Описание: {debtor.description or 'Не указано'}",
                    due_date=today,
                    priority="high",  # Высокий приоритет для финансовых обязательств
                    is_daily=False,
                    is_completed=False
                )
                session.add(todo)
                tasks_created += 1
        
        if tasks_created > 0:
            await session.commit()
            print(f"✅ Создано {tasks_created} задач для финансовых обязательств пользователя {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка при создании задач для финансовых обязательств: {e}")


async def create_todos_for_all_users(session: AsyncSession) -> None:
    """
    Создает задачи для финансовых обязательств всех пользователей.
    """
    try:
        # Получаем всех пользователей
        users = (await session.execute(select(User))).scalars().all()
        
        for user in users:
            await create_todo_for_financial_obligations(session, user.id)
            
    except Exception as e:
        print(f"❌ Ошибка при создании задач для всех пользователей: {e}")


async def cleanup_old_financial_todos(session: AsyncSession, user_id: int) -> None:
    """
    Удаляет старые задачи для финансовых обязательств (старше 7 дней).
    """
    try:
        today = date.today()
        week_ago = today - datetime.timedelta(days=7)
        
        # Удаляем старые задачи для финансовых обязательств
        old_todos = await session.execute(
            select(Todo)
            .where(
                and_(
                    Todo.user_id == user_id,
                    Todo.due_date < week_ago,
                    Todo.description.like("Финансовое обязательство:%"),
                    Todo.is_completed == True  # Удаляем только выполненные
                )
            )
        )
        old_todos_list = old_todos.scalars().all()
        
        for todo in old_todos_list:
            await session.delete(todo)
        
        if old_todos_list:
            await session.commit()
            print(f"🗑️ Удалено {len(old_todos_list)} старых задач для финансовых обязательств пользователя {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке старых задач: {e}")


async def get_financial_todos_for_user(session: AsyncSession, user_id: int) -> List[Todo]:
    """
    Получает все задачи для финансовых обязательств пользователя.
    """
    try:
        result = await session.execute(
            select(Todo)
            .where(
                and_(
                    Todo.user_id == user_id,
                    Todo.description.like("Финансовое обязательство:%")
                )
            )
            .order_by(Todo.due_date.desc())
        )
        return result.scalars().all()
        
    except Exception as e:
        print(f"❌ Ошибка при получении задач для финансовых обязательств: {e}")
        return []
