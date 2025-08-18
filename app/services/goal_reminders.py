import random
from datetime import datetime, time
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Goal, GoalReminder, User
from app.bot import bot


# Мотивирующие сообщения для напоминаний
MOTIVATION_MESSAGES = [
    "Сегодня великий день! Сегодня реализация цели: {goal_title} 🎯✨",
    "Время действовать! Сегодня ты достигаешь цели: {goal_title} 🚀💪",
    "Сегодня особенный день - день достижения цели: {goal_title} 🌟🎉",
    "Помни о своей цели: {goal_title}. Сегодня ты на шаг ближе к успеху! 🔥",
    "Сегодня день, когда ты воплощаешь в жизнь цель: {goal_title} ⭐💫",
    "Твоя цель: {goal_title} ждет реализации сегодня! Время показать, на что ты способен! 🎯🔥",
    "Сегодня великолепный день для достижения цели: {goal_title} ✨🌟",
    "Помни, ради чего ты начал! Сегодня реализация цели: {goal_title} 🎯💪",
    "Сегодня день твоей цели: {goal_title}. Время действовать! 🚀⭐",
    "Сегодня ты становишься ближе к своей мечте! Цель: {goal_title} 🌟🎯"
]


async def get_active_goal_reminders(session: AsyncSession) -> List[Tuple[Goal, GoalReminder, User]]:
    """Получает все активные напоминания по целям."""
    result = (
        await session.execute(
            select(Goal, GoalReminder, User)
            .join(GoalReminder, Goal.id == GoalReminder.goal_id)
            .join(User, Goal.user_id == User.id)
            .where(
                Goal.status == "active",
                GoalReminder.is_active == True
            )
        )
    ).all()
    
    return result


def get_random_motivation_message(goal_title: str) -> str:
    """Возвращает случайное мотивирующее сообщение с названием цели."""
    message_template = random.choice(MOTIVATION_MESSAGES)
    return message_template.format(goal_title=goal_title)


async def send_goal_reminders(session: AsyncSession) -> None:
    """Отправляет напоминания по целям всем пользователям."""
    current_time = datetime.now().time()
    
    # Получаем все активные напоминания
    reminders = await get_active_goal_reminders(session)
    
    for goal, reminder, user in reminders:
        try:
            # Проверяем, подходит ли время для отправки
            reminder_time = time.fromisoformat(reminder.reminder_time)
            
            # Отправляем напоминание если текущее время совпадает с временем напоминания
            # (с погрешностью в 1 минуту)
            time_diff = abs(
                (current_time.hour * 60 + current_time.minute) - 
                (reminder_time.hour * 60 + reminder_time.minute)
            )
            
            if time_diff <= 1:  # В пределах 1 минуты
                # Получаем случайное мотивирующее сообщение
                motivation_message = get_random_motivation_message(goal.title)
                
                # Формируем полное сообщение
                full_message = (
                    f"⏰ Напоминание по цели\n\n"
                    f"{motivation_message}\n\n"
                    f"📅 Срок: {goal.due_date.strftime('%d.%m.%Y') if goal.due_date else 'Не указан'}\n"
                    f"📝 Описание: {goal.description or 'Не указано'}\n\n"
                    f"💪 Действуй сейчас!"
                )
                
                # Отправляем сообщение пользователю
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=full_message,
                    parse_mode=None
                )
                
                print(f"Отправлено напоминание пользователю {user.telegram_id} по цели: {goal.title}")
                
        except Exception as e:
            print(f"Ошибка отправки напоминания пользователю {user.telegram_id}: {e}")


async def send_test_reminder(user_id: int, goal_title: str = "Тестовая цель") -> None:
    """Отправляет тестовое напоминание (для проверки)."""
    try:
        motivation_message = get_random_motivation_message(goal_title)
        
        full_message = (
            f"🧪 **Тестовое напоминание**\n\n"
            f"{motivation_message}\n\n"
            f"📅 **Срок:** Сегодня\n"
            f"📝 **Описание:** Это тестовое напоминание для проверки работы системы\n\n"
            f"💪 **Система напоминаний работает!**"
        )
        
        await bot.send_message(
            chat_id=user_id,
            text=full_message,
            parse_mode="Markdown"
        )
        
        print(f"Отправлено тестовое напоминание пользователю {user_id}")
        
    except Exception as e:
        print(f"Ошибка отправки тестового напоминания пользователю {user_id}: {e}")
