#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы часовых поясов
"""

import sys
import os
from datetime import datetime, timezone

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.timezone_utils import (
    get_user_local_time,
    is_time_to_send_reminder,
    validate_timezone,
    get_timezone_display_name,
    parse_utc_offset
)


def test_timezone_parsing():
    """Тест парсинга UTC смещений"""
    print("🧪 Тестирование парсинга UTC смещений:")
    
    test_cases = [
        "UTC+3",
        "UTC-5", 
        "UTC+0",
        "UTC+12",
        "UTC-12",
        "UTC+3:30",
        "UTC-5:30",
        "invalid",
        "UTC++3",
        "UTC-"
    ]
    
    for case in test_cases:
        result = parse_utc_offset(case)
        print(f"  {case:>10} -> {result}")
    
    print()


def test_timezone_validation():
    """Тест валидации часовых поясов"""
    print("✅ Тестирование валидации часовых поясов:")
    
    test_cases = [
        "Europe/Moscow",
        "America/New_York", 
        "UTC+3",
        "UTC-5",
        "invalid_timezone",
        "Asia/Tokyo",
        "UTC+0",
        "Europe/London"
    ]
    
    for case in test_cases:
        is_valid = validate_timezone(case)
        print(f"  {case:>20} -> {'✅' if is_valid else '❌'}")
    
    print()


def test_user_local_time():
    """Тест получения локального времени пользователя"""
    print("🕐 Тестирование локального времени пользователей:")
    
    test_timezones = [
        "UTC+3",
        "UTC-5",
        "Europe/Moscow",
        "America/New_York",
        "Asia/Tokyo",
        None  # UTC по умолчанию
    ]
    
    utc_now = datetime.now(timezone.utc)
    print(f"  Текущее UTC время: {utc_now.strftime('%H:%M:%S')}")
    
    for tz in test_timezones:
        try:
            local_time = get_user_local_time(tz)
            tz_name = tz or "UTC (по умолчанию)"
            print(f"  {tz_name:>25} -> {local_time.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"  {tz:>25} -> Ошибка: {e}")
    
    print()


def test_reminder_timing():
    """Тест проверки времени для напоминаний"""
    print("⏰ Тестирование времени напоминаний:")
    
    test_cases = [
        ("UTC+3", 7),   # 7:00 UTC+3
        ("UTC-5", 8),   # 8:00 UTC-5
        ("UTC+0", 9),   # 9:00 UTC
        ("Europe/Moscow", 7),  # 7:00 Moscow
        (None, 7)       # 7:00 UTC
    ]
    
    for timezone_str, target_hour in test_cases:
        should_send = is_time_to_send_reminder(timezone_str, target_hour)
        tz_name = timezone_str or "UTC (по умолчанию)"
        print(f"  {tz_name:>25} в {target_hour:02d}:00 -> {'🟢 Отправлять' if should_send else '🔴 Не время'}")
    
    print()


def test_timezone_display_names():
    """Тест отображаемых названий часовых поясов"""
    print("🏷️ Тестирование отображаемых названий:")
    
    test_timezones = [
        "UTC+3",
        "UTC-5", 
        "Europe/Moscow",
        "America/New_York",
        "Asia/Tokyo",
        "invalid_tz"
    ]
    
    for tz in test_timezones:
        display_name = get_timezone_display_name(tz)
        print(f"  {tz:>20} -> {display_name}")
    
    print()


def test_timezone_info():
    """Тест получения информации о часовом поясе"""
    print("ℹ️ Тестирование информации о часовом поясе:")
    
    from app.utils.timezone_utils import get_user_time_info
    
    test_timezones = [
        "UTC+3",
        "UTC-5",
        "Europe/Moscow",
        None
    ]
    
    for tz in test_timezones:
        try:
            info = get_user_time_info(tz)
            tz_name = tz or "UTC (по умолчанию)"
            print(f"  {tz_name:>20}:")
            print(f"    Локальное время: {info['user_local_time'].strftime('%H:%M:%S')}")
            print(f"    UTC время: {info['utc_time'].strftime('%H:%M:%S')}")
            print(f"    Смещение: {info['offset_hours']:+g} ч")
            print(f"    Часовой пояс: {info['timezone']}")
        except Exception as e:
            print(f"  {tz:>20} -> Ошибка: {e}")
        print()


def main():
    """Основная функция тестирования"""
    print("🌍 Тестирование системы часовых поясов Voit Bot")
    print("=" * 60)
    
    try:
        test_timezone_parsing()
        test_timezone_validation()
        test_user_local_time()
        test_reminder_timing()
        test_timezone_display_names()
        test_timezone_info()
        
        print("🎉 Все тесты завершены успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
