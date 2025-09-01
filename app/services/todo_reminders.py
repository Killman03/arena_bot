from datetime import datetime, time
from typing import List, Tuple, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Todo, User
from app.utils.timezone_utils import get_user_time_info

# Кэш для отслеживания отправленных напоминаний: {user_id_task_id: date}
_sent_todo_reminders_cache: Dict[str, str] = {}


async def get_active_todo_reminders(session: AsyncSession) -> List[Tuple[Todo, User]]:
    """Получает все активные задачи с напоминаниями."""
    result = (
        await session.execute(
            select(Todo, User)
            .join(User, Todo.user_id == User.id)
            .where(
                Todo.is_reminder_active == True,
                Todo.reminder_time.isnot(None),
                Todo.is_completed == False
            )
        )
    ).all()
    
    return result


def _cleanup_old_todo_reminders_cache() -> None:
    """Очищает старые записи из кэша отправленных to-do напоминаний."""
    global _sent_todo_reminders_cache
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Удаляем записи старше сегодняшнего дня
    keys_to_remove = [
        key for key, date in _sent_todo_reminders_cache.items() 
        if date != today
    ]
    
    for key in keys_to_remove:
        del _sent_todo_reminders_cache[key]


async def send_todo_reminders(session: AsyncSession, bot=None) -> None:
    """Отправляет напоминания по to-do задачам всем пользователям."""
    if bot is None:
        from app.bot import bot
    
    # Очищаем старые записи из кэша
    _cleanup_old_todo_reminders_cache()
    
    # Получаем все активные задачи с напоминаниями
    todos_with_users = await get_active_todo_reminders(session)
    
    for todo, user in todos_with_users:
        try:
            # Создаем уникальный ключ для этого напоминания
            if todo.is_daily:
                reminder_key = f"{user.id}_{todo.id}_{todo.reminder_time}"
            else:
                # Для разовых задач включаем дату в ключ
                reminder_key = f"{user.id}_{todo.id}_{todo.reminder_time}_{todo.due_date}"
            
            # Проверяем, было ли уже отправлено это напоминание сегодня
            today = datetime.now().strftime("%Y-%m-%d")
            if _sent_todo_reminders_cache.get(reminder_key) == today:
                continue
            
            # Получаем локальное время пользователя
            time_info = get_user_time_info(user.timezone)
            user_local_time = time_info['user_local_time']
            user_local_date = user_local_time.date()
            
            # Проверяем дату выполнения задачи
            if todo.is_daily:
                # Для ежедневных задач - отправляем каждый день
                should_send_today = True
            else:
                # Для разовых задач - отправляем только в день выполнения
                should_send_today = (user_local_date == todo.due_date)
            
            if not should_send_today:
                print(f"⏭️ Пропускаем напоминание по задаче '{todo.title}' - не время (дата выполнения: {todo.due_date}, сегодня: {user_local_date})")
                continue
            
            # Проверяем, подходит ли время для отправки (по локальному времени пользователя)
            reminder_time = time.fromisoformat(todo.reminder_time)
            
            # Отправляем напоминание если локальное время пользователя совпадает с временем напоминания
            # (с погрешностью в 1 минуту)
            time_diff = abs(
                (user_local_time.hour * 60 + user_local_time.minute) - 
                (reminder_time.hour * 60 + reminder_time.minute)
            )
            
            if time_diff <= 1:  # В пределах 1 минуты
                # Логируем локальное время пользователя
                print(f"🕐 Отправка напоминания по задаче '{todo.title}' пользователю {user.telegram_id}")
                print(f"   📍 Часовой пояс: {time_info['timezone']}")
                print(f"   🕐 Локальное время пользователя: {time_info['user_local_time'].strftime('%H:%M:%S')}")
                print(f"   🌍 UTC время: {time_info['utc_time'].strftime('%H:%M:%S')}")
                print(f"   ⏰ Время напоминания: {todo.reminder_time}")
                print(f"   📊 Смещение: {time_info['offset_hours']:+g} ч")
                
                # Формируем сообщение
                if todo.is_daily:
                    message_text = (
                        f"🔔 <b>Напоминание о ежедневной задаче</b>\n\n"
                        f"📝 <b>{todo.title}</b>\n\n"
                        f"🔄 Эта задача повторяется каждый день\n"
                        f"🔴 Приоритет: {todo.priority}\n\n"
                        f"💪 Время действовать!"
                    )
                else:
                    message_text = (
                        f"🔔 <b>Напоминание о задаче</b>\n\n"
                        f"📝 <b>{todo.title}</b>\n"
                        f"📅 <b>Срок:</b> {todo.due_date.strftime('%d.%m.%Y')}\n"
                        f"🔴 <b>Приоритет:</b> {todo.priority}\n\n"
                        f"💪 Время действовать!"
                    )
                
                if todo.description:
                    message_text += f"\n\n📄 <b>Описание:</b>\n{todo.description}"
                
                # Отправляем сообщение пользователю
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message_text,
                    parse_mode="HTML"
                )
                
                # Отмечаем напоминание как отправленное
                _sent_todo_reminders_cache[reminder_key] = today
                
                print(f"Отправлено напоминание пользователю {user.telegram_id} по задаче: {todo.title}")
                
        except Exception as e:
            print(f"Ошибка отправки напоминания пользователю {user.telegram_id}: {e}")


async def send_test_todo_reminder(user_id: int, task_title: str = "Тестовая задача", bot=None) -> None:
    """Отправляет тестовое напоминание по to-do задаче (для проверки)."""
    if bot is None:
        from app.bot import bot
        
    try:
        message_text = (
            f"🧪 <b>Тестовое напоминание по задаче</b>\n\n"
            f"📝 <b>{task_title}</b>\n"
            f"📅 <b>Срок:</b> Сегодня\n"
            f"🔴 <b>Приоритет:</b> Высокий\n\n"
            f"💪 <b>Система напоминаний работает!</b>"
        )
        
        await bot.send_message(
            chat_id=user_id,
            text=message_text,
            parse_mode="HTML"
        )
        
        print(f"Отправлено тестовое напоминание по задаче пользователю {user_id}")
        
    except Exception as e:
        print(f"Ошибка отправки тестового напоминания пользователю {user_id}: {e}")
