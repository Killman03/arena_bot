#!/usr/bin/env python3
"""
Скрипт для тестирования финансовых уведомлений
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import session_scope
from app.db.models import User, Creditor, Debtor
from app.services.finance_reminders import (
    get_overdue_creditors,
    get_overdue_debtors,
    get_upcoming_creditors,
    get_upcoming_debtors,
    send_finance_reminders_for_user
)
from datetime import date, timedelta


class MockBot:
    """Мок-объект бота для тестирования"""
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = None):
        """Имитирует отправку сообщения"""
        print(f"\n📤 СООБЩЕНИЕ ОТПРАВЛЕНО В ЧАТ {chat_id}:")
        print("=" * 50)
        print(text)
        print("=" * 50)
        return True


async def test_finance_reminders():
    """Тестирование финансовых уведомлений"""
    print("🧪 Тестирование финансовых уведомлений...")
    
    # Создаем мок-бот для тестирования
    mock_bot = MockBot()
    
    async with session_scope() as session:
        # Получаем первого пользователя для тестирования
        users = (await session.execute("SELECT id, telegram_id FROM \"user\" LIMIT 1")).fetchall()
        
        if not users:
            print("❌ Пользователи не найдены")
            return
        
        user_id = users[0][0]
        telegram_id = users[0][1]
        
        print(f"👤 Тестируем для пользователя ID: {user_id}, Telegram ID: {telegram_id}")
        
        # Проверяем существующие кредиторы и должники
        overdue_creditors = await get_overdue_creditors(session, user_id)
        overdue_debtors = await get_overdue_debtors(session, user_id)
        upcoming_creditors = await get_upcoming_creditors(session, user_id)
        upcoming_debtors = await get_upcoming_debtors(session, user_id)
        
        print(f"📊 Статистика:")
        print(f"   🔴 Просроченных кредиторов: {len(overdue_creditors)}")
        print(f"   🔴 Просроченных должников: {len(overdue_debtors)}")
        print(f"   🟡 Приближающихся кредиторов: {len(upcoming_creditors)}")
        print(f"   🟡 Приближающихся должников: {len(upcoming_debtors)}")
        
        # Если нет данных для тестирования, создаем тестовые записи
        if not (overdue_creditors or overdue_debtors or upcoming_creditors or upcoming_debtors):
            print("📝 Создаем тестовые финансовые записи...")
            
            # Создаем просроченного кредитора
            overdue_creditor = Creditor(
                user_id=user_id,
                name="Тестовый банк",
                amount=5000.00,
                due_date=date.today() - timedelta(days=5),
                description="Тестовый просроченный кредит"
            )
            session.add(overdue_creditor)
            
            # Создаем просроченного должника
            overdue_debtor = Debtor(
                user_id=user_id,
                name="Иван Петров",
                amount=3000.00,
                due_date=date.today() - timedelta(days=3),
                description="Тестовый просроченный долг"
            )
            session.add(overdue_debtor)
            
            # Создаем приближающегося кредитора
            upcoming_creditor = Creditor(
                user_id=user_id,
                name="Кредитная карта",
                amount=15000.00,
                due_date=date.today() + timedelta(days=2),
                description="Тестовый приближающийся кредит"
            )
            session.add(upcoming_creditor)
            
            # Создаем приближающегося должника
            upcoming_debtor = Debtor(
                user_id=user_id,
                name="Мария Сидорова",
                amount=8000.00,
                due_date=date.today() + timedelta(days=1),
                description="Тестовый приближающийся долг"
            )
            session.add(upcoming_debtor)
            
            await session.commit()
            print("✅ Тестовые записи созданы")
        
        # Тестируем отправку уведомлений
        print("📤 Тестируем отправку уведомлений...")
        try:
            await send_finance_reminders_for_user(session, user_id, mock_bot)
            print("✅ Уведомления отправлены успешно")
        except Exception as e:
            print(f"❌ Ошибка при отправке уведомлений: {e}")


if __name__ == "__main__":
    asyncio.run(test_finance_reminders())
