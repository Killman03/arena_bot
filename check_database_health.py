#!/usr/bin/env python3
"""
Скрипт для проверки состояния базы данных и данных пользователей
Использование: python3 check_database_health.py
"""

import asyncio
import sys
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Импортируем модели
sys.path.append('.')
from app.db.models import User, Todo, Goal, Finance, Health, Nutrition, Productivity, Routine, Interaction
from app.config import settings


async def check_database_health():
    """Проверка состояния базы данных"""
    
    print("🔍 Проверка состояния базы данных...")
    print("=" * 50)
    
    # Создаем подключение к БД
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            
            # 1. Проверка подключения
            print("1. Проверка подключения к БД...")
            result = await session.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"   ✅ Подключение успешно. PostgreSQL версия: {version}")
            
            # 2. Проверка таблиц
            print("\n2. Проверка таблиц...")
            tables = [
                'users', 'todos', 'goals', 'finances', 'health', 
                'nutrition', 'productivity', 'routines', 'interactions'
            ]
            
            for table in tables:
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table};"))
                    count = result.scalar()
                    print(f"   ✅ Таблица {table}: {count} записей")
                except Exception as e:
                    print(f"   ❌ Таблица {table}: ошибка - {e}")
            
            # 3. Детальная проверка пользователей
            print("\n3. Детальная проверка пользователей...")
            
            # Общее количество пользователей
            result = await session.execute(text("SELECT COUNT(*) FROM users;"))
            total_users = result.scalar()
            print(f"   Всего пользователей: {total_users}")
            
            # Пользователи за последние 30 дней
            result = await session.execute(text("""
                SELECT COUNT(*) FROM users 
                WHERE created_at >= NOW() - INTERVAL '30 days';
            """))
            recent_users = result.scalar()
            print(f"   Новых пользователей за 30 дней: {recent_users}")
            
            # Пользователи с настройками timezone
            result = await session.execute(text("""
                SELECT COUNT(*) FROM users 
                WHERE timezone IS NOT NULL;
            """))
            users_with_tz = result.scalar()
            print(f"   Пользователей с настройками timezone: {users_with_tz}")
            
            # 4. Проверка активных задач
            print("\n4. Проверка активных задач...")
            
            # Общее количество задач
            result = await session.execute(text("SELECT COUNT(*) FROM todos;"))
            total_todos = result.scalar()
            print(f"   Всего задач: {total_todos}")
            
            # Активные задачи
            result = await session.execute(text("""
                SELECT COUNT(*) FROM todos 
                WHERE is_completed = false;
            """))
            active_todos = result.scalar()
            print(f"   Активных задач: {active_todos}")
            
            # Задачи с напоминаниями
            result = await session.execute(text("""
                SELECT COUNT(*) FROM todos 
                WHERE is_reminder_active = true;
            """))
            todos_with_reminders = result.scalar()
            print(f"   Задач с напоминаниями: {todos_with_reminders}")
            
            # 5. Проверка финансовых данных
            print("\n5. Проверка финансовых данных...")
            
            result = await session.execute(text("SELECT COUNT(*) FROM finances;"))
            total_finances = result.scalar()
            print(f"   Всего финансовых записей: {total_finances}")
            
            # 6. Проверка целей
            print("\n6. Проверка целей...")
            
            result = await session.execute(text("SELECT COUNT(*) FROM goals;"))
            total_goals = result.scalar()
            print(f"   Всего целей: {total_goals}")
            
            # 7. Проверка последних взаимодействий
            print("\n7. Проверка последних взаимодействий...")
            
            result = await session.execute(text("""
                SELECT COUNT(*) FROM interactions 
                WHERE created_at >= NOW() - INTERVAL '24 hours';
            """))
            recent_interactions = result.scalar()
            print(f"   Взаимодействий за последние 24 часа: {recent_interactions}")
            
            # 8. Проверка размера БД
            print("\n8. Проверка размера базы данных...")
            
            result = await session.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database()));
            """))
            db_size = result.scalar()
            print(f"   Размер базы данных: {db_size}")
            
            # 9. Проверка индексов
            print("\n9. Проверка индексов...")
            
            result = await session.execute(text("""
                SELECT schemaname, tablename, indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' 
                ORDER BY tablename, indexname;
            """))
            indexes = result.fetchall()
            
            for index in indexes:
                print(f"   📊 {index[1]}.{index[2]}")
            
            # 10. Проверка последних ошибок (если есть таблица логов)
            print("\n10. Проверка состояния системы...")
            
            # Проверка времени последнего обновления
            result = await session.execute(text("""
                SELECT MAX(updated_at) FROM users;
            """))
            last_update = result.scalar()
            if last_update:
                print(f"   Последнее обновление пользователя: {last_update}")
            
            print("\n" + "=" * 50)
            print("✅ Проверка завершена успешно!")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке БД: {e}")
        return False
    
    finally:
        await engine.dispose()
    
    return True


async def check_data_integrity():
    """Проверка целостности данных"""
    
    print("\n🔍 Проверка целостности данных...")
    print("=" * 50)
    
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            
            # Проверка пользователей без telegram_id
            result = await session.execute(text("""
                SELECT COUNT(*) FROM users WHERE telegram_id IS NULL;
            """))
            users_without_tg = result.scalar()
            if users_without_tg > 0:
                print(f"   ⚠️  Пользователей без telegram_id: {users_without_tg}")
            else:
                print("   ✅ Все пользователи имеют telegram_id")
            
            # Проверка дубликатов telegram_id
            result = await session.execute(text("""
                SELECT telegram_id, COUNT(*) 
                FROM users 
                GROUP BY telegram_id 
                HAVING COUNT(*) > 1;
            """))
            duplicates = result.fetchall()
            if duplicates:
                print(f"   ⚠️  Найдено дубликатов telegram_id: {len(duplicates)}")
                for dup in duplicates[:5]:  # Показываем первые 5
                    print(f"      telegram_id {dup[0]}: {dup[1]} записей")
            else:
                print("   ✅ Дубликатов telegram_id не найдено")
            
            # Проверка задач без пользователей
            result = await session.execute(text("""
                SELECT COUNT(*) FROM todos t 
                LEFT JOIN users u ON t.user_id = u.id 
                WHERE u.id IS NULL;
            """))
            orphan_todos = result.scalar()
            if orphan_todos > 0:
                print(f"   ⚠️  Задач без пользователей: {orphan_todos}")
            else:
                print("   ✅ Все задачи привязаны к пользователям")
            
            print("\n✅ Проверка целостности завершена!")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке целостности: {e}")
        return False
    
    finally:
        await engine.dispose()
    
    return True


async def main():
    """Основная функция"""
    
    print("🚀 Запуск проверки состояния Voit Bot")
    print("=" * 50)
    
    # Проверка конфигурации
    try:
        print(f"База данных: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'Неизвестно'}")
    except Exception as e:
        print(f"Ошибка чтения конфигурации: {e}")
        return
    
    # Выполняем проверки
    db_ok = await check_database_health()
    integrity_ok = await check_data_integrity()
    
    print("\n" + "=" * 50)
    if db_ok and integrity_ok:
        print("🎉 Все проверки пройдены успешно!")
        print("✅ База данных готова к обновлению")
    else:
        print("❌ Обнаружены проблемы!")
        print("⚠️  Рекомендуется исправить проблемы перед обновлением")


if __name__ == "__main__":
    asyncio.run(main())
