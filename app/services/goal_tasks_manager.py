from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Goal, Todo, User
from app.db.models.goal import GoalStatus, GoalScope
from app.services.llm import deepseek_complete


class GoalTasksManager:
    """Менеджер для создания ежедневных задач на основе целей пользователя."""
    
    @staticmethod
    async def create_daily_tasks_from_goals(session: AsyncSession, user_id: int) -> List[Todo]:
        """
        Создает ежедневные задачи на основе активных целей пользователя.
        
        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            
        Returns:
            Список созданных задач
        """
        # Получаем все активные цели пользователя
        goals = await session.execute(
            select(Goal).where(
                and_(
                    Goal.user_id == user_id,
                    Goal.status == GoalStatus.active
                )
            )
        )
        goals_list = goals.scalars().all()
        
        if not goals_list:
            return []
        
        created_tasks = []
        today = date.today()
        
        for goal in goals_list:
            # Генерируем ежедневную задачу на основе цели
            daily_task = await GoalTasksManager._generate_daily_task_from_goal(
                session, goal, today
            )
            
            if daily_task:
                session.add(daily_task)
                created_tasks.append(daily_task)
        
        if created_tasks:
            await session.commit()
            print(f"Создано {len(created_tasks)} ежедневных задач на основе целей для пользователя {user_id}")
        
        return created_tasks
    
    @staticmethod
    async def _generate_daily_task_from_goal(
        session: AsyncSession, 
        goal: Goal, 
        task_date: date
    ) -> Optional[Todo]:
        """
        Генерирует ежедневную задачу на основе цели.
        
        Args:
            session: Сессия базы данных
            goal: Цель пользователя
            task_date: Дата для задачи
            
        Returns:
            Созданная задача или None
        """
        # Все задачи на основе целей получают высокий приоритет
        priority = GoalTasksManager._get_priority_from_goal_scope(goal.scope)
        
        # Генерируем название задачи на основе цели
        task_title = await GoalTasksManager._generate_task_title_from_goal(goal)
        
        # Проверяем, не существует ли уже такая задача на сегодня
        existing_task = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == goal.user_id,
                    Todo.title == task_title,
                    Todo.due_date == task_date,
                    Todo.is_daily == True
                )
            )
        )
        
        if existing_task.scalar_one_or_none():
            # Задача уже существует, не создаем дубликат
            return None
        
        # Создаем новую задачу
        daily_task = Todo(
            user_id=goal.user_id,
            title=task_title,
            description=f"Ежедневная задача для достижения цели: {goal.title}",
            due_date=task_date,
            priority=priority,
            is_daily=True,
            is_completed=False,
            reminder_time=None,  # Напоминания будут через систему целей
            is_reminder_active=False
        )
        
        return daily_task
    
    @staticmethod
    def _get_priority_from_goal_scope(scope: GoalScope) -> str:
        """Определяет приоритет задачи на основе scope цели.
        
        Все задачи на основе целей получают высокий приоритет,
        так как они важны для достижения пользовательских целей.
        """
        # Все задачи на основе целей получают высокий приоритет
        return "high"
    
    @staticmethod
    async def _generate_task_title_from_goal(goal: Goal) -> str:
        """
        Генерирует название ежедневной задачи на основе цели.
        Использует AI для создания конкретных действий.
        """
        try:
            # Формируем промпт для AI
            prompt = f"""
            Цель пользователя: {goal.title}
            Описание: {goal.description or 'Не указано'}
            Срок: {goal.due_date.strftime('%d.%m.%Y') if goal.due_date else 'Не указан'}
            
            Создай конкретную ежедневную задачу для достижения этой цели. 
            Задача должна быть:
            - Конкретной и измеримой
            - Выполнимой за день
            - Начинаться с глагола действия
            
            Примеры:
            - Цель: "Выучить английский" → Задача: "Заниматься английским 30 минут"
            - Цель: "Похудеть" → Задача: "Сделать 30 минут кардио"
            - Цель: "Прочитать 12 книг" → Задача: "Читать книгу 20 минут"
            
            Верни только название задачи без кавычек и дополнительных символов.
            """
            
            task_title = await deepseek_complete(
                prompt, 
                system="Ты помощник по постановке целей. Создавай конкретные ежедневные задачи."
            )
            
            # Очищаем результат от лишних символов
            task_title = task_title.strip().strip('"').strip("'").strip()
            
            # Если AI не сработал, создаем базовое название
            if not task_title or len(task_title) < 3:
                task_title = f"Работать над целью: {goal.title[:50]}"
            
            return task_title
            
        except Exception as e:
            print(f"Ошибка генерации названия задачи для цели {goal.id}: {e}")
            # Fallback - создаем базовое название
            return f"Работать над целью: {goal.title[:50]}"
    
    @staticmethod
    async def reset_daily_goal_tasks(session: AsyncSession, user_id: int) -> None:
        """
        Сбрасывает статус ежедневных задач, созданных на основе целей.
        
        Args:
            session: Сессия базы данных
            user_id: ID пользователя
        """
        today = date.today()
        
        # Находим все ежедневные задачи пользователя, созданные на основе целей
        daily_tasks = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == user_id,
                    Todo.is_daily == True,
                    Todo.description.like("Ежедневная задача для достижения цели:%"),
                    Todo.due_date == today
                )
            )
        )
        daily_tasks_list = daily_tasks.scalars().all()
        
        for task in daily_tasks_list:
            task.is_completed = False
        
        if daily_tasks_list:
            await session.commit()
            print(f"Сброшено {len(daily_tasks_list)} ежедневных задач на основе целей для пользователя {user_id}")
    
    @staticmethod
    async def get_daily_goal_tasks_summary(session: AsyncSession, user_id: int) -> dict:
        """
        Получает сводку по ежедневным задачам на основе целей.
        
        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            
        Returns:
            Словарь со статистикой
        """
        today = date.today()
        
        # Все ежедневные задачи на основе целей на сегодня
        all_tasks = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == user_id,
                    Todo.is_daily == True,
                    Todo.description.like("Ежедневная задача для достижения цели:%"),
                    Todo.due_date == today
                )
            )
        )
        all_tasks_list = all_tasks.scalars().all()
        
        # Выполненные задачи
        completed_tasks = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == user_id,
                    Todo.is_daily == True,
                    Todo.description.like("Ежедневная задача для достижения цели:%"),
                    Todo.due_date == today,
                    Todo.is_completed == True
                )
            )
        )
        completed_list = completed_tasks.scalars().all()
        
        return {
            "total": len(all_tasks_list),
            "completed": len(completed_list),
            "pending": len(all_tasks_list) - len(completed_list),
            "completion_rate": (len(completed_list) / len(all_tasks_list) * 100) if all_tasks_list else 0
        }
    
    @staticmethod
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
        cutoff_date = date.today() - datetime.timedelta(days=days_to_keep)
        
        # Находим старые выполненные задачи на основе целей
        old_tasks = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == user_id,
                    Todo.is_daily == True,
                    Todo.description.like("Ежедневная задача для достижения цели:%"),
                    Todo.due_date < cutoff_date,
                    Todo.is_completed == True
                )
            )
        )
        old_tasks_list = old_tasks.scalars().all()
        
        deleted_count = 0
        for task in old_tasks_list:
            await session.delete(task)
            deleted_count += 1
        
        if deleted_count > 0:
            await session.commit()
            print(f"Удалено {deleted_count} старых выполненных задач на основе целей для пользователя {user_id}")
        
        return deleted_count
