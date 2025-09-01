from __future__ import annotations

from datetime import date, datetime
from typing import List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Todo, User
from app.services.goal_tasks_manager import GoalTasksManager


async def reset_daily_tasks(session: AsyncSession, user_id: int) -> None:
    """
    Сбрасывает ежедневные задачи для пользователя на новый день.
    
    Логика:
    1. Сбрасывает обычные ежедневные задачи
    2. Сбрасывает задачи на основе целей
    3. Создает новые задачи на основе активных целей
    """
    try:
        # Сбрасываем обычные ежедневные задачи
        daily_todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == user_id,
                    Todo.is_daily == True,
                    Todo.description.notlike("Ежедневная задача для достижения цели:%")
                )
            )
        )
        daily_todos_list = daily_todos.scalars().all()
        
        today = date.today()
        
        for todo in daily_todos_list:
            # Сбрасываем статус выполнения
            todo.is_completed = False
            
            # Обновляем дату на сегодня
            todo.due_date = today
        
        # Сбрасываем задачи на основе целей
        await GoalTasksManager.reset_daily_goal_tasks(session, user_id)
        
        # Создаем новые задачи на основе активных целей
        await GoalTasksManager.create_daily_tasks_from_goals(session, user_id)
        
        # Сохраняем изменения
        await session.commit()
        
        print(f"Сброшено {len(daily_todos_list)} обычных ежедневных задач для пользователя {user_id}")
        
    except Exception as e:
        print(f"Ошибка при сбросе ежедневных задач: {e}")
        await session.rollback()


async def get_daily_tasks_for_today(session: AsyncSession, user_id: int) -> List[Todo]:
    """Получает ежедневные задачи на сегодня"""
    today = date.today()
    
    daily_todos = await session.execute(
        select(Todo).where(
            and_(
                Todo.user_id == user_id,
                Todo.is_daily == True,
                Todo.due_date == today
            )
        ).order_by(Todo.priority)
    )
    
    return daily_todos.scalars().all()


async def create_daily_task_copy(session: AsyncSession, user_id: int, original_todo: Todo) -> Todo:
    """
    Создает копию ежедневной задачи на новый день.
    Используется только когда пользователь явно хочет скопировать задачу.
    """
    new_todo = Todo(
        user_id=user_id,
        title=original_todo.title,
        description=original_todo.description,
        due_date=date.today(),
        priority=original_todo.priority,
        is_daily=False,  # Копия не является ежедневной
        created_at=datetime.now()
    )
    
    session.add(new_todo)
    await session.commit()
    
    return new_todo


async def mark_daily_task_completed(session: AsyncSession, todo_id: int, user_id: int) -> bool:
    """Отмечает ежедневную задачу как выполненную"""
    try:
        todo = await session.execute(
            select(Todo).where(
                and_(
                    Todo.id == todo_id,
                    Todo.user_id == user_id,
                    Todo.is_daily == True
                )
            )
        )
        todo_obj = todo.scalar_one_or_none()
        
        if todo_obj:
            todo_obj.is_completed = True
            todo_obj.updated_at = datetime.now()
            await session.commit()
            return True
        
        return False
        
    except Exception as e:
        print(f"Ошибка при отметке задачи как выполненной: {e}")
        await session.rollback()
        return False


async def get_daily_tasks_summary(session: AsyncSession, user_id: int) -> dict:
    """Получает сводку по ежедневным задачам на сегодня"""
    today = date.today()
    
    # Все ежедневные задачи на сегодня
    all_daily = await session.execute(
        select(Todo).where(
            and_(
                Todo.user_id == user_id,
                Todo.is_daily == True,
                Todo.due_date == today
            )
        )
    )
    all_daily_list = all_daily.scalars().all()
    
    # Выполненные задачи
    completed_daily = await session.execute(
        select(Todo).where(
            and_(
                Todo.user_id == user_id,
                Todo.is_daily == True,
                Todo.due_date == today,
                Todo.is_completed == True
            )
        )
    )
    completed_list = completed_daily.scalars().all()
    
    return {
        "total": len(all_daily_list),
        "completed": len(completed_list),
        "pending": len(all_daily_list) - len(completed_list),
        "completion_rate": (len(completed_list) / len(all_daily_list) * 100) if all_daily_list else 0
    }


async def create_goal_based_tasks(session: AsyncSession, user_id: int) -> List[Todo]:
    """
    Создает ежедневные задачи на основе активных целей пользователя.
    
    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        
    Returns:
        Список созданных задач
    """
    return await GoalTasksManager.create_daily_tasks_from_goals(session, user_id)


async def get_goal_based_tasks_summary(session: AsyncSession, user_id: int) -> dict:
    """
    Получает сводку по ежедневным задачам на основе целей.
    
    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        
    Returns:
        Словарь со статистикой
    """
    return await GoalTasksManager.get_daily_goal_tasks_summary(session, user_id)


async def cleanup_old_goal_tasks(session: AsyncSession, user_id: int, days_to_keep: int = 7) -> int:
    """
    Удаляет старые выполненные задачи на основе целей.
    
    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        days_to_keep: Количество дней для хранения выполненных задач
        
    Returns:
        Количество удаленных задач
    """
    return await GoalTasksManager.cleanup_old_goal_tasks(session, user_id, days_to_keep)


async def get_separate_daily_tasks_summary(session: AsyncSession, user_id: int) -> dict:
    """
    Получает отдельную сводку по обычным ежедневным задачам и задачам на основе целей.
    
    Args:
        session: Сессия базы данных
        user_id: ID пользователя
        
    Returns:
        Словарь с отдельной статистикой
    """
    today = date.today()
    
    # Обычные ежедневные задачи
    regular_daily = await session.execute(
        select(Todo).where(
            and_(
                Todo.user_id == user_id,
                Todo.is_daily == True,
                Todo.due_date == today,
                Todo.description.notlike("Ежедневная задача для достижения цели:%")
            )
        )
    )
    regular_list = regular_daily.scalars().all()
    
    # Задачи на основе целей
    goal_based = await session.execute(
        select(Todo).where(
            and_(
                Todo.user_id == user_id,
                Todo.is_daily == True,
                Todo.due_date == today,
                Todo.description.like("Ежедневная задача для достижения цели:%")
            )
        )
    )
    goal_list = goal_based.scalars().all()
    
    # Выполненные обычные задачи
    completed_regular = await session.execute(
        select(Todo).where(
            and_(
                Todo.user_id == user_id,
                Todo.is_daily == True,
                Todo.due_date == today,
                Todo.is_completed == True,
                Todo.description.notlike("Ежедневная задача для достижения цели:%")
            )
        )
    )
    completed_regular_list = completed_regular.scalars().all()
    
    # Выполненные задачи на основе целей
    completed_goal = await session.execute(
        select(Todo).where(
            and_(
                Todo.user_id == user_id,
                Todo.is_daily == True,
                Todo.due_date == today,
                Todo.is_completed == True,
                Todo.description.like("Ежедневная задача для достижения цели:%")
            )
        )
    )
    completed_goal_list = completed_goal.scalars().all()
    
    return {
        "regular": {
            "total": len(regular_list),
            "completed": len(completed_regular_list),
            "pending": len(regular_list) - len(completed_regular_list),
            "completion_rate": (len(completed_regular_list) / len(regular_list) * 100) if regular_list else 0
        },
        "goal_based": {
            "total": len(goal_list),
            "completed": len(completed_goal_list),
            "pending": len(goal_list) - len(completed_goal_list),
            "completion_rate": (len(completed_goal_list) / len(goal_list) * 100) if goal_list else 0
        },
        "total": {
            "total": len(regular_list) + len(goal_list),
            "completed": len(completed_regular_list) + len(completed_goal_list),
            "pending": (len(regular_list) - len(completed_regular_list)) + (len(goal_list) - len(completed_goal_list)),
            "completion_rate": ((len(completed_regular_list) + len(completed_goal_list)) / (len(regular_list) + len(goal_list)) * 100) if (regular_list or goal_list) else 0
        }
    }
