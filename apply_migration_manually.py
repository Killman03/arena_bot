#!/usr/bin/env python3
"""
Скрипт для ручного применения миграции добавления поля end_date
"""

import asyncio
import asyncpg
from datetime import datetime


async def apply_migration():
    """Применяет миграцию для добавления поля end_date в таблицу challenge"""
    
    # Параметры подключения к базе данных
    # Измените их в соответствии с вашими настройками
    DATABASE_URL = "postgresql://postgres:1234567890@localhost:5432/arena_bot"
    
    try:
        # Подключаемся к базе данных
        print("🔌 Подключение к базе данных...")
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Проверяем, существует ли уже поле end_date
        print("🔍 Проверка существования поля end_date...")
        check_query = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'challenge' AND column_name = 'end_date'
        """
        result = await conn.fetch(check_query)
        
        if result:
            print("✅ Поле end_date уже существует")
            return
        
        # Добавляем поле end_date
        print("➕ Добавление поля end_date...")
        alter_query = """
        ALTER TABLE challenge 
        ADD COLUMN end_date DATE
        """
        await conn.execute(alter_query)
        
        print("✅ Поле end_date успешно добавлено")
        
        # Проверяем результат
        print("🔍 Проверка результата...")
        check_result = await conn.fetch(check_query)
        if check_result:
            print("✅ Поле end_date подтверждено в базе данных")
        else:
            print("❌ Ошибка: поле end_date не найдено после добавления")
            
    except asyncpg.InvalidPasswordError:
        print("❌ Ошибка аутентификации: неверный пароль")
    except asyncpg.InvalidAuthorizationSpecificationError:
        print("❌ Ошибка авторизации: неверное имя пользователя или база данных")
    except asyncpg.ConnectionDoesNotExistError:
        print("❌ Ошибка подключения: база данных не существует")
    except asyncpg.ConnectionError as e:
        print(f"❌ Ошибка подключения: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()
            print("🔌 Соединение с базой данных закрыто")


if __name__ == "__main__":
    print("🚀 Запуск ручного применения миграции...")
    print("📋 Добавление поля end_date в таблицу challenge")
    print("=" * 50)
    
    try:
        asyncio.run(apply_migration())
    except KeyboardInterrupt:
        print("\n⏹️ Операция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка выполнения: {e}")
    
    print("\n📋 Следующие шаги:")
    print("1. Убедитесь, что миграция применена успешно")
    print("2. Раскомментируйте код в файлах:")
    print("   - app/db/models/challenge.py")
    print("   - app/handlers/challenges.py")
    print("   - app/keyboards/common.py")
    print("   - app/utils/scheduler.py")
    print("3. Перезапустите бота")
