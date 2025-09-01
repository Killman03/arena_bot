from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz
import re


def get_user_local_time(user_timezone: Optional[str]) -> datetime:
    """
    Получает текущее локальное время пользователя.
    Если часовой пояс не указан, возвращает UTC.
    """
    if not user_timezone:
        return datetime.now(timezone.utc)
    
    try:
        # Получаем текущее время в UTC
        utc_now = datetime.now(timezone.utc)
        
        # Обрабатываем формат UTC+3, UTC-5
        if user_timezone.startswith("UTC"):
            offset = parse_utc_offset(user_timezone)
            if offset is not None:
                user_local_time = utc_now + timedelta(hours=offset)
                return user_local_time
        
        # Конвертируем в часовой пояс пользователя
        user_tz = pytz.timezone(user_timezone)
        user_local_time = utc_now.astimezone(user_tz)
        
        return user_local_time
    except (pytz.exceptions.UnknownTimeZoneError, Exception):
        # В случае ошибки возвращаем UTC
        return datetime.now(timezone.utc)


def parse_utc_offset(timezone_str: str) -> Optional[int]:
    """
    Парсит строку формата UTC+3, UTC-5 и возвращает смещение в часах.
    
    Args:
        timezone_str: Строка в формате UTC+3, UTC-5, UTC+3:30 и т.д.
    
    Returns:
        Смещение в часах (может быть дробным для UTC+3:30)
    """
    # Паттерн для UTC+3, UTC-5, UTC+3:30
    pattern = r'^UTC([+-])(\d{1,2})(?::(\d{2}))?$'
    match = re.match(pattern, timezone_str)
    
    if match:
        sign = match.group(1)
        hours = int(match.group(2))
        minutes = int(match.group(3)) if match.group(3) else 0
        
        # Конвертируем минуты в часы
        total_hours = hours + (minutes / 60)
        
        if sign == '-':
            total_hours = -total_hours
        
        return int(total_hours)
    
    return None


def is_time_to_send_reminder(user_timezone: Optional[str], target_hour: int, 
                           window_minutes: int = 1) -> bool:
    """
    Проверяет, пора ли отправлять напоминание пользователю.
    
    Args:
        user_timezone: Часовой пояс пользователя (например, "Europe/Moscow" или "UTC+3")
        target_hour: Целевой час для отправки (например, 7 для 7:00)
        window_minutes: Окно времени в минутах для отправки (по умолчанию 15)
    
    Returns:
        True, если пора отправлять напоминание
    """
    user_local_time = get_user_local_time(user_timezone)
    
    # Проверяем, попадает ли текущее время в целевое окно
    if user_local_time.hour == target_hour:
        return 0 <= user_local_time.minute < window_minutes
    
    return False


def get_user_time_info(user_timezone: Optional[str]) -> dict:
    """
    Получает информацию о времени пользователя.
    
    Returns:
        Словарь с информацией о времени
    """
    user_local_time = get_user_local_time(user_timezone)
    utc_time = datetime.now(timezone.utc)
    
    # Вычисляем смещение в часах
    if user_timezone and user_timezone.startswith("UTC"):
        offset = parse_utc_offset(user_timezone)
        offset_hours = offset if offset is not None else 0
    else:
        offset_hours = user_local_time.utcoffset().total_seconds() / 3600 if user_local_time.utcoffset() else 0
    
    return {
        "user_local_time": user_local_time,
        "utc_time": utc_time,
        "timezone": user_timezone or "UTC",
        "offset_hours": offset_hours
    }


def format_time_for_user(user_timezone: Optional[str], time_obj: datetime) -> str:
    """
    Форматирует время для отображения пользователю в его часовом поясе.
    """
    if not user_timezone:
        return time_obj.strftime("%H:%M UTC")
    
    try:
        if user_timezone.startswith("UTC"):
            offset = parse_utc_offset(user_timezone)
            if offset is not None:
                user_time = time_obj + timedelta(hours=offset)
                return user_time.strftime("%H:%M")
        
        user_tz = pytz.timezone(user_timezone)
        user_time = time_obj.astimezone(user_tz)
        return user_time.strftime("%H:%M %Z")
    except (pytz.exceptions.UnknownTimeZoneError, Exception):
        return time_obj.strftime("%H:%M UTC")


def get_next_reminder_time(user_timezone: Optional[str], target_hour: int) -> datetime:
    """
    Получает время следующего напоминания для пользователя.
    """
    user_local_time = get_user_local_time(user_timezone)
    
    # Если текущий час больше целевого, напоминание будет завтра
    if user_local_time.hour >= target_hour:
        next_time = user_local_time.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        next_time += timedelta(days=1)
    else:
        next_time = user_local_time.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    
    return next_time


# Предустановленные часовые пояса для удобства пользователей
COMMON_TIMEZONES = {
    "Europe/Moscow": "Москва (UTC+3)",
    "Europe/London": "Лондон (UTC+0/+1)",
    "America/New_York": "Нью-Йорк (UTC-5/-4)",
    "America/Los_Angeles": "Лос-Анджелес (UTC-8/-7)",
    "Asia/Tokyo": "Токио (UTC+9)",
    "Asia/Shanghai": "Шанхай (UTC+8)",
    "Australia/Sydney": "Сидней (UTC+10/+11)",
    "Asia/Dubai": "Дубай (UTC+4)",
    "Asia/Kolkata": "Мумбаи (UTC+5:30)",
    "Europe/Berlin": "Берлин (UTC+1/+2)",
    "Europe/Paris": "Париж (UTC+1/+2)",
    "Asia/Seoul": "Сеул (UTC+9)",
    "America/Chicago": "Чикаго (UTC-6/-5)",
    "America/Toronto": "Торонто (UTC-5/-4)",
    "Asia/Singapore": "Сингапур (UTC+8)",
    "Europe/Istanbul": "Стамбул (UTC+3)",
    "Africa/Cairo": "Каир (UTC+2)",
    "Asia/Jakarta": "Джакарта (UTC+7)",
    "America/Sao_Paulo": "Сан-Паулу (UTC-3/-2)",
    "Asia/Bangkok": "Бангкок (UTC+7)",
    "UTC+3": "UTC+3 (Москва, Стамбул)",
    "UTC+5": "UTC+5 (Екатеринбург, Ташкент)",
    "UTC+8": "UTC+8 (Пекин, Сингапур)",
    "UTC+9": "UTC+9 (Токио, Сеул)",
    "UTC-5": "UTC-5 (Нью-Йорк, Торонто)",
    "UTC-8": "UTC-8 (Лос-Анджелес)",
    "UTC+0": "UTC+0 (Лондон, Лиссабон)"
}


def get_timezone_display_name(timezone_str: str) -> str:
    """
    Получает человекочитаемое название часового пояса.
    """
    return COMMON_TIMEZONES.get(timezone_str, timezone_str)


def validate_timezone(timezone_str: str) -> bool:
    """
    Проверяет, является ли строка валидным часовым поясом.
    Поддерживает как стандартные часовые пояса, так и формат UTC+3.
    """
    # Проверяем формат UTC+3, UTC-5
    if timezone_str.startswith("UTC"):
        return parse_utc_offset(timezone_str) is not None
    
    # Проверяем стандартные часовые пояса
    try:
        pytz.timezone(timezone_str)
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        return False


def get_timezone_offset_display(timezone_str: str) -> str:
    """
    Получает отображаемое смещение часового пояса.
    """
    if timezone_str.startswith("UTC"):
        offset = parse_utc_offset(timezone_str)
        if offset is not None:
            sign = "+" if offset >= 0 else ""
            return f"UTC{sign}{offset}"
    
    try:
        tz = pytz.timezone(timezone_str)
        now = datetime.now(timezone.utc)
        offset = tz.utcoffset(now)
        if offset:
            hours = int(offset.total_seconds() / 3600)
            sign = "+" if hours >= 0 else ""
            return f"UTC{sign}{hours}"
    except:
        pass
    
    return timezone_str

