#!/usr/bin/env python3
"""
Скрипт для применения миграции книг
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку в путь
sys.path.append(str(Path(__file__).parent))

from alembic.config import Config
from alembic import command


def apply_migration():
    """Применить миграцию книг"""
    try:
        # Создаем конфигурацию Alembic
        alembic_cfg = Config("alembic.ini")
        
        # Применяем миграцию
        print("🔄 Применяю миграцию книг...")
        command.upgrade(alembic_cfg, "004")
        print("✅ Миграция успешно применена!")
        
        print("\n📚 Раздел книг добавлен в бота!")
        print("Теперь вы можете:")
        print("• Добавлять книги для чтения")
        print("• Отслеживать прогресс чтения")
        print("• Сохранять цитаты и мысли")
        print("• Получать советы от ИИ")
        print("• Анализировать статистику чтения")
        
    except Exception as e:
        print(f"❌ Ошибка при применении миграции: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
