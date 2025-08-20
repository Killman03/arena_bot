#!/usr/bin/env python3
"""
Скрипт для проверки настроек базы данных
"""

import os
from pathlib import Path


def check_database_config():
    """Проверяет настройки базы данных"""
    
    print("🔍 Проверка настроек базы данных...")
    print("=" * 50)
    
    # Проверяем переменные окружения
    print("📋 Переменные окружения:")
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print(f"✅ DATABASE_URL: {database_url}")
    else:
        print("❌ DATABASE_URL не установлена")
    
    # Проверяем файл .env
    env_file = Path(".env")
    if env_file.exists():
        print(f"✅ Файл .env найден: {env_file}")
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "DATABASE_URL" in content:
                    print("✅ DATABASE_URL найдена в .env")
                    # Показываем строку с DATABASE_URL
                    for line in content.split('\n'):
                        if line.startswith('DATABASE_URL'):
                            print(f"   {line}")
                else:
                    print("❌ DATABASE_URL не найдена в .env")
        except Exception as e:
            print(f"❌ Ошибка чтения .env: {e}")
    else:
        print("❌ Файл .env не найден")
    
    # Проверяем alembic.ini
    alembic_file = Path("alembic.ini")
    if alembic_file.exists():
        print(f"✅ Файл alembic.ini найден: {alembic_file}")
        try:
            with open(alembic_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "sqlalchemy.url" in content:
                    print("✅ sqlalchemy.url найдена в alembic.ini")
                    # Показываем строку с sqlalchemy.url
                    for line in content.split('\n'):
                        if line.startswith('sqlalchemy.url'):
                            print(f"   {line}")
                else:
                    print("❌ sqlalchemy.url не найдена в alembic.ini")
        except Exception as e:
            print(f"❌ Ошибка чтения alembic.ini: {e}")
    else:
        print("❌ Файл alembic.ini не найден")
    
    print("\n📋 Рекомендации:")
    if not database_url and not env_file.exists():
        print("1. Создайте файл .env на основе env.example")
        print("2. Укажите правильный DATABASE_URL")
        print("3. Пример: DATABASE_URL=postgresql://user:pass@localhost:5432/dbname")
    elif not database_url:
        print("1. Проверьте содержимое файла .env")
        print("2. Убедитесь, что DATABASE_URL указана правильно")
    else:
        print("1. DATABASE_URL настроена")
        print("2. Проверьте, что база данных доступна")
        print("3. Попробуйте подключиться к базе данных")


if __name__ == "__main__":
    check_database_config()
