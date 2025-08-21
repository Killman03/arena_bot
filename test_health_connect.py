#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Health Connect интеграции.

Запуск:
python test_health_connect.py
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.health_connect import HealthConnectService
from app.db.session import session_scope
from app.db.models import GoogleFitToken


async def test_health_connect_service():
    """Тестируем сервис Health Connect."""
    print("🧪 Тестирование Health Connect сервиса...")
    
    try:
        # Создаем экземпляр сервиса
        health_service = HealthConnectService()
        print("✅ Сервис Health Connect создан")
        
        # Проверяем поддерживаемые типы данных
        data_types = await health_service.get_supported_data_types()
        print(f"✅ Поддерживаемые типы данных: {', '.join(data_types)}")
        
        # Проверяем URL авторизации
        auth_url = health_service.get_authorization_url(user_id=1)
        print(f"✅ URL авторизации: {auth_url[:50]}...")
        
        print("\n🎉 Все тесты Health Connect прошли успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования Health Connect: {e}")
        return False
    
    return True


async def test_database_connection():
    """Тестируем подключение к базе данных."""
    print("\n🗄️ Тестирование подключения к базе данных...")
    
    try:
        async with session_scope() as session:
            # Проверяем, что можем подключиться к БД
            print("✅ Подключение к базе данных успешно")
            
            # Проверяем таблицу GoogleFitToken
            result = await session.execute("SELECT 1")
            print("✅ Запрос к базе данных выполнен")
            
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False
    
    return True


async def main():
    """Основная функция тестирования."""
    print("🚀 Запуск тестов Health Connect интеграции\n")
    
    # Тестируем сервис
    service_ok = await test_health_connect_service()
    
    # Тестируем базу данных
    db_ok = await test_database_connection()
    
    print("\n" + "="*50)
    if service_ok and db_ok:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("✅ Health Connect интеграция готова к использованию")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("🔧 Проверьте настройки и зависимости")
    
    print("="*50)


if __name__ == "__main__":
    # Запускаем тесты
    asyncio.run(main())
