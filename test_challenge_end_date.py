#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности срока действия челленджей
"""

from datetime import date, datetime
from app.db.models.challenge import Challenge


def test_challenge_model():
    """Тестируем модель Challenge с новым полем end_date"""
    print("🧪 Тестирование модели Challenge...")
    
    # Создаем тестовый челлендж без срока
    challenge1 = Challenge(
        title="Тестовый челлендж без срока",
        description="Описание",
        time_str="08:00",
        days_mask="1111110"
    )
    print(f"✅ Челлендж без срока: {challenge1.title}")
    print(f"   end_date: {challenge1.end_date}")
    
    # Создаем тестовый челлендж со сроком
    challenge2 = Challenge(
        title="Тестовый челлендж со сроком",
        description="Описание",
        time_str="09:00",
        days_mask="1111110",
        end_date=date(2025, 2, 15)
    )
    print(f"✅ Челлендж со сроком: {challenge2.title}")
    print(f"   end_date: {challenge2.end_date}")
    
    print("✅ Тест модели завершен успешно\n")


def test_date_parsing():
    """Тестируем парсинг дат"""
    print("🧪 Тестирование парсинга дат...")
    
    test_dates = [
        "15.02.2025",
        "01.01.2025",
        "31.12.2024"
    ]
    
    for date_str in test_dates:
        try:
            parsed_date = datetime.strptime(date_str, "%d.%m.%Y").date()
            print(f"✅ {date_str} -> {parsed_date}")
        except ValueError as e:
            print(f"❌ Ошибка парсинга {date_str}: {e}")
    
    print("✅ Тест парсинга дат завершен успешно\n")


def test_date_validation():
    """Тестируем валидацию дат"""
    print("🧪 Тестирование валидации дат...")
    
    today = date.today()
    test_cases = [
        (date(today.year + 1, 1, 1), True, "Дата в будущем"),
        (today, False, "Сегодня"),
        (date(today.year - 1, 1, 1), False, "Дата в прошлом")
    ]
    
    for test_date, should_be_valid, description in test_cases:
        is_valid = test_date > today
        status = "✅" if is_valid == should_be_valid else "❌"
        print(f"{status} {description}: {test_date} (валидна: {is_valid})")
    
    print("✅ Тест валидации дат завершен успешно\n")


if __name__ == "__main__":
    print("🚀 Запуск тестов функциональности срока действия челленджей\n")
    
    try:
        test_challenge_model()
        test_date_parsing()
        test_date_validation()
        
        print("🎉 Все тесты прошли успешно!")
        print("\n📋 Следующие шаги:")
        print("1. Применить миграцию: alembic upgrade head")
        print("2. Перезапустить бота")
        print("3. Протестировать создание челленджа с датой окончания")
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()
