from __future__ import annotations

from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Dict
import random

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Creditor, Debtor, User
from app.utils.timezone_utils import get_user_time_info

# Глобальный словарь для отслеживания отправленных напоминаний
# Формат: {reminder_key: last_sent_date}
_sent_reminders_cache: Dict[str, str] = {}

# Мотивирующие сообщения для финансовых напоминаний
FINANCE_MOTIVATION_MESSAGES = [
    "💰 Время проверить финансовые обязательства!",
    "💸 Не забудь про финансовые дела!",
    "🏦 Проверь свои долги и кредиты!",
    "💳 Время разобраться с финансами!",
    "📊 Финансовая дисциплина - путь к успеху!",
    "💵 Контроль финансов - контроль жизни!",
    "💰 Финансовое здоровье требует внимания!",
    "💸 Держи финансы под контролем!",
    "🏦 Время финансовой проверки!",
    "💳 Управляй своими деньгами мудро!"
]


async def get_overdue_creditors(session: AsyncSession, user_id: int) -> List[Creditor]:
    """Получает просроченных кредиторов пользователя."""
    today = date.today()
    result = await session.execute(
        select(Creditor)
        .where(
            and_(
                Creditor.user_id == user_id,
                Creditor.is_active == True,
                Creditor.due_date < today
            )
        )
        .order_by(Creditor.due_date)
    )
    return result.scalars().all()


async def get_overdue_debtors(session: AsyncSession, user_id: int) -> List[Debtor]:
    """Получает просроченных должников пользователя."""
    today = date.today()
    result = await session.execute(
        select(Debtor)
        .where(
            and_(
                Debtor.user_id == user_id,
                Debtor.is_active == True,
                Debtor.due_date < today
            )
        )
        .order_by(Debtor.due_date)
    )
    return result.scalars().all()


async def get_upcoming_creditors(session: AsyncSession, user_id: int, days_ahead: int = 3) -> List[Creditor]:
    """Получает кредиторов с приближающимися сроками выплат."""
    today = date.today()
    future_date = today + timedelta(days=days_ahead)
    result = await session.execute(
        select(Creditor)
        .where(
            and_(
                Creditor.user_id == user_id,
                Creditor.is_active == True,
                Creditor.due_date >= today,
                Creditor.due_date <= future_date
            )
        )
        .order_by(Creditor.due_date)
    )
    return result.scalars().all()


async def get_upcoming_debtors(session: AsyncSession, user_id: int, days_ahead: int = 3) -> List[Debtor]:
    """Получает должников с приближающимися сроками выплат."""
    today = date.today()
    future_date = today + timedelta(days=days_ahead)
    result = await session.execute(
        select(Debtor)
        .where(
            and_(
                Debtor.user_id == user_id,
                Debtor.is_active == True,
                Debtor.due_date >= today,
                Debtor.due_date <= future_date
            )
        )
        .order_by(Debtor.due_date)
    )
    return result.scalars().all()


def get_random_finance_message() -> str:
    """Возвращает случайное мотивирующее сообщение для финансов."""
    return random.choice(FINANCE_MOTIVATION_MESSAGES)


def _cleanup_old_reminders_cache() -> None:
    """Очищает старые записи из кэша отправленных напоминаний."""
    global _sent_reminders_cache
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Удаляем записи старше сегодняшнего дня
    keys_to_remove = [
        key for key, date in _sent_reminders_cache.items() 
        if date != today
    ]
    
    for key in keys_to_remove:
        del _sent_reminders_cache[key]


async def send_finance_reminders(session: AsyncSession, bot=None) -> None:
    """Отправляет финансовые напоминания всем пользователям."""
    if bot is None:
        print("⚠️ Бот не передан, пропускаем отправку сообщений")
        return
    
    # Очищаем старые записи из кэша
    _cleanup_old_reminders_cache()
    
    # Получаем всех пользователей
    users = (await session.execute(select(User))).scalars().all()
    
    for user in users:
        await send_finance_reminders_for_user(session, user.id, bot)


async def send_finance_reminders_for_user(session: AsyncSession, user_id: int, bot=None) -> None:
    """Отправляет финансовые напоминания конкретному пользователю."""
    if bot is None:
        print("⚠️ Бот не передан, пропускаем отправку сообщения")
        return
    
    try:
        # Получаем пользователя
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        
        # Проверяем настройки уведомлений
        prefs = user.notification_preferences or {}
        if not prefs.get("finance_reminders", True):
            return
        
        # Создаем уникальный ключ для этого пользователя
        reminder_key = f"{user.id}_finance_reminders"
        
        # Проверяем, было ли уже отправлено напоминание сегодня
        today = datetime.now().strftime("%Y-%m-%d")
        if _sent_reminders_cache.get(reminder_key) == today:
            return
        
        # Получаем локальное время пользователя
        time_info = get_user_time_info(user.timezone)
        user_local_time = time_info['user_local_time']
        
        # Проверяем, пора ли отправлять напоминание (9:00 по местному времени пользователя)
        reminder_time = time(9, 0)  # 9:00 утра
        
        # Отправляем напоминание если локальное время пользователя совпадает с временем напоминания
        # (с погрешностью в 1 минуту)
        time_diff = abs(
            (user_local_time.hour * 60 + user_local_time.minute) - 
            (reminder_time.hour * 60 + reminder_time.minute)
        )
        
        if time_diff <= 1:
            # Получаем финансовые данные
            overdue_creditors = await get_overdue_creditors(session, user.id)
            overdue_debtors = await get_overdue_debtors(session, user.id)
            upcoming_creditors = await get_upcoming_creditors(session, user.id)
            upcoming_debtors = await get_upcoming_debtors(session, user.id)
            
            # Формируем сообщение
            message = await _format_finance_reminder_message(
                overdue_creditors, overdue_debtors, 
                upcoming_creditors, upcoming_debtors
            )
            
            if message:
                # Отправляем сообщение
                await bot.send_message(
                    user.telegram_id,
                    message,
                    parse_mode="HTML"
                )
                
                # Отмечаем как отправленное
                _sent_reminders_cache[reminder_key] = today
                
                print(f"✅ Финансовое напоминание отправлено пользователю {user.telegram_id}")
            
    except Exception as e:
        print(f"❌ Ошибка при отправке финансового напоминания пользователю {user_id}: {e}")


async def _format_finance_reminder_message(
    overdue_creditors: List[Creditor],
    overdue_debtors: List[Debtor],
    upcoming_creditors: List[Creditor],
    upcoming_debtors: List[Debtor]
) -> str:
    """Форматирует сообщение с финансовыми напоминаниями."""
    message_parts = []
    
    # Заголовок
    message_parts.append("💰 <b>Финансовые напоминания</b>\n")
    
    # Просроченные кредиторы (вам должны)
    if overdue_creditors:
        message_parts.append("🔴 <b>Просроченные выплаты (вам должны):</b>")
        for creditor in overdue_creditors:
            days_overdue = (date.today() - creditor.due_date).days
            message_parts.append(
                f"• {creditor.name}: {float(creditor.amount):,.2f} ₽ "
                f"(просрочено на {days_overdue} дн.)"
            )
        message_parts.append("")
    
    # Просроченные должники (вы должны)
    if overdue_debtors:
        message_parts.append("🔴 <b>Просроченные долги (вы должны):</b>")
        for debtor in overdue_debtors:
            days_overdue = (date.today() - debtor.due_date).days
            message_parts.append(
                f"• {debtor.name}: {float(debtor.amount):,.2f} ₽ "
                f"(просрочено на {days_overdue} дн.)"
            )
        message_parts.append("")
    
    # Приближающиеся кредиторы (вам должны)
    if upcoming_creditors:
        message_parts.append("🟡 <b>Приближающиеся выплаты (вам должны):</b>")
        for creditor in upcoming_creditors:
            days_until = (creditor.due_date - date.today()).days
            message_parts.append(
                f"• {creditor.name}: {float(creditor.amount):,.2f} ₽ "
                f"(через {days_until} дн.)"
            )
        message_parts.append("")
    
    # Приближающиеся должники (вы должны)
    if upcoming_debtors:
        message_parts.append("🟡 <b>Приближающиеся долги (вы должны):</b>")
        for debtor in upcoming_debtors:
            days_until = (debtor.due_date - date.today()).days
            message_parts.append(
                f"• {debtor.name}: {float(debtor.amount):,.2f} ₽ "
                f"(через {days_until} дн.)"
            )
        message_parts.append("")
    
    # Если нет никаких напоминаний
    if not (overdue_creditors or overdue_debtors or upcoming_creditors or upcoming_debtors):
        message_parts.append("✅ Все финансовые обязательства в порядке!")
        message_parts.append("")
    
    # Мотивирующее сообщение
    message_parts.append(f"💪 {get_random_finance_message()}")
    
    # Кнопка для перехода в финансы
    message_parts.append("\n💼 <b>Управление финансами:</b> /finance")
    
    return "\n".join(message_parts)


async def send_urgent_finance_reminder(session: AsyncSession, user_id: int, bot=None) -> None:
    """Отправляет срочное финансовое напоминание конкретному пользователю."""
    if bot is None:
        print("⚠️ Бот не передан, пропускаем отправку срочного уведомления")
        return
    
    try:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        
        # Получаем финансовые данные
        overdue_creditors = await get_overdue_creditors(session, user_id)
        overdue_debtors = await get_overdue_debtors(session, user_id)
        
        if overdue_creditors or overdue_debtors:
            message = await _format_finance_reminder_message(
                overdue_creditors, overdue_debtors, [], []
            )
            
            await bot.send_message(
                user.telegram_id,
                f"🚨 <b>СРОЧНОЕ УВЕДОМЛЕНИЕ!</b>\n\n{message}",
                parse_mode="HTML"
            )
            
            print(f"🚨 Срочное финансовое уведомление отправлено пользователю {user.telegram_id}")
            
    except Exception as e:
        print(f"❌ Ошибка при отправке срочного финансового уведомления: {e}")
