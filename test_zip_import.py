#!/usr/bin/env python3
"""
Тестовый скрипт для проверки импорта ZIP файлов.
"""

import asyncio
import tempfile
import zipfile
import sqlite3
import os
from datetime import datetime, date

from app.services.zip_importer import ZipImporterService
from app.db.session import session_scope
from app.db.models import User


async def create_test_zip():
    """Создает тестовый ZIP файл с данными здоровья."""
    # Создаем временную директорию
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаем тестовую SQLite базу
        db_path = os.path.join(temp_dir, "test_health.db")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу с данными здоровья
        cursor.execute("""
            CREATE TABLE health_data (
                id INTEGER PRIMARY KEY,
                date TEXT,
                steps INTEGER,
                calories INTEGER,
                sleep_minutes INTEGER,
                heart_rate INTEGER,
                weight_kg REAL
            )
        """)
        
        # Добавляем тестовые данные
        test_data = [
            ("2024-01-01", 8500, 2100, 480, 72, 75.5),
            ("2024-01-02", 9200, 2300, 510, 68, 75.3),
            ("2024-01-03", 7800, 1950, 450, 70, 75.4),
            ("2024-01-04", 10500, 2600, 540, 65, 75.1),
            ("2024-01-05", 6800, 1700, 420, 73, 75.6),
        ]
        
        cursor.executemany(
            "INSERT INTO health_data (date, steps, calories, sleep_minutes, heart_rate, weight_kg) VALUES (?, ?, ?, ?, ?, ?)",
            test_data
        )
        
        conn.commit()
        conn.close()
        
        # Создаем ZIP файл
        zip_path = os.path.join(temp_dir, "test_health.zip")
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(db_path, "health_data.db")
        
        print(f"✅ Создан тестовый ZIP файл: {zip_path}")
        print(f"📊 Содержит {len(test_data)} записей о здоровье")
        
        return zip_path


async def test_import():
    """Тестирует импорт данных."""
    print("🧪 Тестирование импорта ZIP файлов...")
    
    # Создаем тестовый ZIP
    zip_path = await create_test_zip()
    
    # Создаем тестового пользователя
    test_user_id = 999999  # Временный ID для теста
    
    # Тестируем импорт
    importer = ZipImporterService()
    
    try:
        async with session_scope() as session:
            # Проверяем, что файл существует
            if not os.path.exists(zip_path):
                print("❌ ZIP файл не найден!")
                return
            
            print(f"📥 Импортирую данные из: {zip_path}")
            
            # Импортируем данные
            result = await importer.import_health_data_from_zip(
                session, test_user_id, zip_path
            )
            
            if result['success']:
                print("✅ Импорт успешен!")
                print(f"📊 Записей импортировано: {result['total_records']}")
                print(f"📋 Таблицы: {', '.join(result['tables_imported'])}")
                
                # Показываем детали импорта
                for table_name, table_data in result['imported_data'].items():
                    print(f"\n📋 Таблица: {table_name}")
                    print(f"   Колонки: {', '.join(table_data['columns'])}")
                    print(f"   Записей: {table_data['count']}")
                    
                    # Показываем первые 3 записи
                    for i, row in enumerate(table_data['rows'][:3]):
                        print(f"   Запись {i+1}: {row}")
                    
                    if len(table_data['rows']) > 3:
                        print(f"   ... и еще {len(table_data['rows']) - 3} записей")
                
            else:
                print(f"❌ Ошибка импорта: {result['error']}")
                
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Очищаем временные файлы
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print("🧹 Временные файлы очищены")


async def test_zip_validation():
    """Тестирует валидацию ZIP файлов."""
    print("\n🔍 Тестирование валидации ZIP файлов...")
    
    importer = ZipImporterService()
    
    # Тест 1: Поддерживаемые форматы
    print(f"📁 Поддерживаемые форматы: {importer.get_supported_formats()}")
    print(f"🗄️ Поддерживаемые БД: {importer.get_db_extensions()}")
    
    # Тест 2: Создание поврежденного ZIP
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
        temp_file.write(b"This is not a ZIP file!")
        temp_path = temp_file.name
    
    try:
        # Должно вызвать ошибку
        result = await importer.import_health_data_from_zip(
            None, 1, temp_path
        )
        print(f"📊 Результат теста поврежденного файла: {result}")
        
    except Exception as e:
        print(f"✅ Ожидаемая ошибка для поврежденного файла: {e}")
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


async def main():
    """Основная функция тестирования."""
    print("🚀 Запуск тестов импорта ZIP файлов")
    print("=" * 50)
    
    # Тест 1: Валидация
    await test_zip_validation()
    
    # Тест 2: Импорт
    await test_import()
    
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(main())
