from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, NutritionReminder, CookingSession
from app.services.llm import deepseek_complete


def _weekday_str_to_int(name: str) -> int:
    # Monday=0 ... Sunday=6
    mapping = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    return mapping[name]


async def send_cooking_day_reminders(bot: Bot, session: AsyncSession) -> None:
    now_utc = datetime.now(timezone.utc)
    users = (await session.execute(select(User))).scalars().all()
    for user in users:
        tz_name = user.timezone or settings.default_timezone
        try:
            user_now = now_utc.astimezone(ZoneInfo(tz_name))
        except Exception:
            user_now = now_utc.astimezone(ZoneInfo(settings.default_timezone))
        rem = (
            await session.execute(select(NutritionReminder).where(NutritionReminder.user_id == user.id))
        ).scalar_one_or_none()
        if not rem or not rem.is_active:
            continue
        # Check if today is a cooking day
        days = [d.strip().lower() for d in (rem.cooking_days or "").split(",") if d.strip()]
        weekday = user_now.weekday()
        if weekday not in [
            _weekday_str_to_int(d) for d in days if d in {"sunday", "wednesday", "monday", "tuesday", "thursday", "friday", "saturday"}
        ]:
            continue
        if user_now.strftime("%H:%M") != rem.reminder_time:
            continue
        try:
            await bot.send_message(user.telegram_id, "🍽️ Напоминание: сегодня день готовки. Удачи на кухне!")
        except Exception:
            continue


async def send_shopping_day_reminders(bot: Bot, session: AsyncSession) -> None:
    now_utc = datetime.now(timezone.utc)
    users = (await session.execute(select(User))).scalars().all()
    for user in users:
        tz_name = user.timezone or settings.default_timezone
        try:
            user_now = now_utc.astimezone(ZoneInfo(tz_name))
        except Exception:
            user_now = now_utc.astimezone(ZoneInfo(settings.default_timezone))
        rem = (
            await session.execute(select(NutritionReminder).where(NutritionReminder.user_id == user.id))
        ).scalar_one_or_none()
        if not rem or not rem.is_active:
            continue
        days = [d.strip().lower() for d in (rem.cooking_days or "").split(",") if d.strip()]
        # Shopping reminder comes a day BEFORE a cooking day -> today is shopping if tomorrow is cooking
        tomorrow_weekday = (user_now.weekday() + 1) % 7
        if tomorrow_weekday not in [
            _weekday_str_to_int(d) for d in days if d in {"sunday", "wednesday", "monday", "tuesday", "thursday", "friday", "saturday"}
        ]:
            continue
        if user_now.strftime("%H:%M") != rem.shopping_reminder_time:
            continue
        # Generate shopping list and calories using AI
        try:
            system = (
                "Ты нутрициолог и кулинар. Составь список покупок (с количеством) для готовки на 2 дня из доступных и недорогих продуктов."
                " Дай также краткий план готовки и примерную калорийность на день."
            )
            prompt = (
                f"Цель: {rem.body_goal or 'maintain'}. Целевые калории: {rem.target_calories or '—'}."
                " Формат ответа: Список покупок на 2 дня; Инструкции; Калории/день (число)."
            )
            ai_text = await deepseek_complete(prompt, system=system, max_tokens=700)
        except Exception as e:
            ai_text = f"Не удалось получить список покупок от ИИ: {e}"
        try:
            header = "🛒 Напоминание о покупках на завтра:"
            await bot.send_message(user.telegram_id, header)
            parts = _split_into_two_messages(ai_text)
            if parts:
                await bot.send_message(user.telegram_id, parts[0])
            if len(parts) > 1:
                await bot.send_message(user.telegram_id, parts[1])
        except Exception:
            continue


def _split_into_two_messages(text: str, max_len: int = 3000) -> list[str]:
    """Разбить текст на несколько сообщений для лучшей читаемости"""
    if not text:
        return []
    
    # Если текст короткий, не разбиваем
    if len(text) <= max_len:
        return [text]
    
    # Если текст очень длинный (>4000), разбиваем на 3 части
    if len(text) > 4000:
        print(f"DEBUG: Текст очень длинный ({len(text)} символов), разбиваю на 3 части")
        part_size = len(text) // 3
        
        # Ищем хорошие точки разрыва
        split1 = part_size
        split2 = part_size * 2
        
        # Ищем ближайшие переносы строк или пробелы
        for i in range(part_size - 100, part_size + 100):
            if i < 0 or i >= len(text):
                continue
            if text[i] == '\n' or text[i] == ' ':
                split1 = i + 1
                break
        
        for i in range(part_size * 2 - 100, part_size * 2 + 100):
            if i < 0 or i >= len(text):
                continue
            if text[i] == '\n' or text[i] == ' ':
                split2 = i + 1
                break
        
        part1 = text[:split1].strip()
        part2 = text[split1:split2].strip()
        part3 = text[split2:].strip()
        
        if part1 and part2 and part3:
            return [part1, part2, part3]
        elif part1 and part2:
            return [part1, part2]
        else:
            return [text]
    
    # Стандартное разбиение на 2 части
    paragraphs = text.split("\n\n")
    total_len = len(text)
    target = total_len // 2
    part1 = []
    len1 = 0
    
    for p in paragraphs:
        block = p + "\n\n"
        if len1 + len(block) <= max_len and (len1 + len(block) <= target or len1 == 0):
            part1.append(block)
            len1 += len(block)
        else:
            break
    
    p1 = "".join(part1).rstrip()
    rest = text[len(p1):].lstrip()
    
    if not p1:
        p1 = text[:max_len]
        rest = text[max_len:]
    
    if len(rest) <= max_len:
        return [p1, rest] if rest else [p1]
    
    # Если вторая часть слишком длинная, разбиваем её тоже
    if len(rest) > max_len:
        print(f"DEBUG: Вторая часть слишком длинная ({len(rest)} символов), разбиваю её")
        mid_point = len(rest) // 2
        for i in range(mid_point - 100, mid_point + 100):
            if i < 0 or i >= len(rest):
                continue
            if rest[i] == '\n' or rest[i] == ' ':
                mid_point = i + 1
                break
        
        part2 = rest[:mid_point].strip()
        part3 = rest[mid_point:].strip()
        
        if part2 and part3:
            return [p1, part2, part3]
        else:
            return [p1, rest[:max_len - 1] + "…"]
    
    return [p1, rest]
