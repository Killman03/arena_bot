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


async def send_cooking_day_reminders(bot: Bot, session: AsyncSession, user_id: int = None) -> None:
    now_utc = datetime.now(timezone.utc)
    if user_id:
        # Отправляем напоминание конкретному пользователю
        users = (await session.execute(select(User).where(User.id == user_id))).scalars().all()
    else:
        # Отправляем напоминания всем пользователям
        users = (await session.execute(select(User))).scalars().all()
    for user in users:
        tz_name = user.timezone or settings.DEFAULT_TIMEZONE
        try:
            user_now = now_utc.astimezone(ZoneInfo(tz_name))
        except Exception:
            user_now = now_utc.astimezone(ZoneInfo(settings.DEFAULT_TIMEZONE))
        rem = (
            await session.execute(select(NutritionReminder).where(NutritionReminder.user_id == user.id))
        ).scalar_one_or_none()
        if not rem or not rem.is_active:
            continue
        # Check if today is a cooking day
        days = [d.strip().lower() for d in (rem.cooking_days or "").split(",") if d.strip()]
        weekday = user_now.weekday()
        weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        current_day_name = weekday_names[weekday]
        
        print(f"🔍 Проверка дней готовки для пользователя {user.telegram_id}:")
        print(f"   📅 Настроенные дни: {rem.cooking_days}")
        print(f"   📅 Парсированные дни: {days}")
        print(f"   📅 Сегодня: {current_day_name} (weekday={weekday})")
        print(f"   📅 Дни готовки: {[_weekday_str_to_int(d) for d in days if d in {'sunday', 'wednesday', 'monday', 'tuesday', 'thursday', 'friday', 'saturday'}]}")
        
        if weekday not in [
            _weekday_str_to_int(d) for d in days if d in {"sunday", "wednesday", "monday", "tuesday", "thursday", "friday", "saturday"}
        ]:
            print(f"   ❌ Сегодня не день готовки для пользователя {user.telegram_id}")
            continue
        if user_now.strftime("%H:%M") != rem.reminder_time:
            continue
        
        # Генерируем план питания с помощью ИИ
        try:
            # Получаем информацию о бюджете питания пользователя
            from app.handlers.nutrition_budget import get_user_food_budget
            budget_info = await get_user_food_budget(session, user.id)
            
            # Добавляем информацию о целях пользователя к budget_info
            if rem.body_goal:
                budget_info = budget_info or {}
                budget_info["body_goal"] = rem.body_goal
            if rem.target_calories:
                budget_info = budget_info or {}
                budget_info["target_calories"] = rem.target_calories
            
            # Генерируем план питания
            from app.services.nutrition_plan_generator import generate_cooking_plan, generate_fallback_plan
            try:
                plan_text = await generate_cooking_plan(budget_info)
                if not plan_text or len(plan_text.strip()) < 10:
                    plan_text = generate_fallback_plan(budget_info, "Пустой ответ от ИИ")
            except Exception as e:
                plan_text = generate_fallback_plan(budget_info, str(e))
            
            # Сохраняем в базу
            from app.db.models import CookingSession
            from datetime import date
            session.add(CookingSession(user_id=user.id, cooking_date=date.today(), instructions=plan_text))
            await session.commit()
            
            # Отправляем заголовок с информацией о бюджете
            budget_text = f" (бюджет: {budget_info['description']})" if budget_info and budget_info["type"] else ""
            header_text = f"👨‍🍳 План готовки на 2 дня{budget_text}:"
            await bot.send_message(user.telegram_id, header_text, parse_mode="HTML")
            
            # Конвертируем Markdown в HTML для корректного отображения
            plan_text_html = _convert_markdown_to_html(plan_text)
            
            # Разбиваем на части и отправляем
            parts = _split_into_multiple_messages(plan_text_html)
            
            # Отправляем все части
            for i, part in enumerate(parts):
                await bot.send_message(user.telegram_id, part, parse_mode="HTML")
                
        except Exception as e:
            # Если не удалось сгенерировать план, отправляем простое напоминание
            try:
                await bot.send_message(user.telegram_id, "🍽️ Напоминание: сегодня день готовки. Удачи на кухне!")
            except Exception:
                continue


async def send_shopping_day_reminders(bot: Bot, session: AsyncSession, user_id: int = None) -> None:
    now_utc = datetime.now(timezone.utc)
    if user_id:
        # Отправляем напоминание конкретному пользователю
        users = (await session.execute(select(User).where(User.id == user_id))).scalars().all()
    else:
        # Отправляем напоминания всем пользователям
        users = (await session.execute(select(User))).scalars().all()
    for user in users:
        tz_name = user.timezone or settings.DEFAULT_TIMEZONE
        try:
            user_now = now_utc.astimezone(ZoneInfo(tz_name))
        except Exception:
            user_now = now_utc.astimezone(ZoneInfo(settings.DEFAULT_TIMEZONE))
        rem = (
            await session.execute(select(NutritionReminder).where(NutritionReminder.user_id == user.id))
        ).scalar_one_or_none()
        if not rem or not rem.is_active:
            continue
        days = [d.strip().lower() for d in (rem.cooking_days or "").split(",") if d.strip()]
        # Shopping reminder comes a day BEFORE a cooking day -> today is shopping if tomorrow is cooking
        tomorrow_weekday = (user_now.weekday() + 1) % 7
        weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        current_day_name = weekday_names[user_now.weekday()]
        tomorrow_day_name = weekday_names[tomorrow_weekday]
        
        print(f"🛒 Проверка дней покупок для пользователя {user.telegram_id}:")
        print(f"   📅 Настроенные дни готовки: {rem.cooking_days}")
        print(f"   📅 Парсированные дни: {days}")
        print(f"   📅 Сегодня: {current_day_name} (weekday={user_now.weekday()})")
        print(f"   📅 Завтра: {tomorrow_day_name} (weekday={tomorrow_weekday})")
        print(f"   📅 Дни готовки: {[_weekday_str_to_int(d) for d in days if d in {'sunday', 'wednesday', 'monday', 'tuesday', 'thursday', 'friday', 'saturday'}]}")
        
        if tomorrow_weekday not in [
            _weekday_str_to_int(d) for d in days if d in {"sunday", "wednesday", "monday", "tuesday", "thursday", "friday", "saturday"}
        ]:
            print(f"   ❌ Завтра не день готовки для пользователя {user.telegram_id}")
            continue
        if user_now.strftime("%H:%M") != rem.shopping_reminder_time:
            continue
        # Generate shopping list and calories using AI
        try:
            # Получаем информацию о бюджете питания пользователя
            from app.handlers.nutrition_budget import get_user_food_budget
            budget_info = await get_user_food_budget(session, user.id)
            
            # Добавляем информацию о целях пользователя к budget_info
            if rem.body_goal:
                budget_info = budget_info or {}
                budget_info["body_goal"] = rem.body_goal
            if rem.target_calories:
                budget_info = budget_info or {}
                budget_info["target_calories"] = rem.target_calories
            
            # Используем тот же генератор планов для консистентности
            from app.services.nutrition_plan_generator import generate_cooking_plan, generate_fallback_plan
            try:
                ai_text = await generate_cooking_plan(budget_info)
                if not ai_text or len(ai_text.strip()) < 10:
                    ai_text = generate_fallback_plan(budget_info, "Пустой ответ от ИИ")
            except Exception as e:
                ai_text = generate_fallback_plan(budget_info, str(e))
        except Exception as e:
            ai_text = f"Не удалось получить список покупок от ИИ: {e}"
        try:
            # Отправляем заголовок
            header = "🛒 Напоминание о покупках на завтра:"
            await bot.send_message(user.telegram_id, header)
            
            # Конвертируем Markdown в HTML для корректного отображения
            ai_text_html = _convert_markdown_to_html(ai_text)
            
            # Разбиваем на части и отправляем
            parts = _split_into_multiple_messages(ai_text_html)
            
            # Отправляем все части
            for i, part in enumerate(parts):
                await bot.send_message(user.telegram_id, part, parse_mode="HTML")
        except Exception:
            continue


def _convert_markdown_to_html(text: str) -> str:
    """Конвертировать Markdown разметку в HTML теги для Telegram"""
    if not text:
        return text
    
    import re
    
    # Конвертируем **текст** в <b>текст</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Конвертируем *текст* в <i>текст</i> (курсив)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # Конвертируем `текст` в <code>текст</code> (моноширинный шрифт)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    # Конвертируем ## Заголовок в <b>Заголовок</b>
    text = re.sub(r'^##\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # Конвертируем # Заголовок в <b>Заголовок</b>
    text = re.sub(r'^#\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # Конвертируем - пункт в • пункт (для лучшей читаемости)
    text = re.sub(r'^\s*-\s+', r'• ', text, flags=re.MULTILINE)
    
    # Конвертируем * пункт в • пункт (для лучшей читаемости)
    text = re.sub(r'^\s*\*\s+', r'• ', text, flags=re.MULTILINE)
    
    return text


def _split_into_multiple_messages(text: str, max_len: int = 3000) -> list[str]:
    """Разбить текст на столько сообщений, сколько нужно для полного отображения.
    Специально оптимизировано для планов питания от DeepSeek.
    """
    if not text:
        return []
    
    # Принудительно разбиваем планы длиннее 1500 символов для лучшей читаемости
    force_split_threshold = 1500
    
    if len(text) <= force_split_threshold:
        return [text]
    
    # Для планов питания ищем логические точки разрыва
    lines = text.split('\n')
    
    # Ищем ключевые разделы плана питания
    section_indicators = [
        '📋', '🛒', '📝', '👨‍🍳', '🔥', '💵', '💰', '🍽️', '🥗', '🥩',
        'Список покупок:', 'Покупки:', 'Инструкции:', 'Рецепты:', 
        'Калории:', 'Стоимость:', 'Бюджет:', 'План на день',
        'День 1:', 'День 2:', 'Завтрак:', 'Обед:', 'Ужин:', 'Перекус:'
    ]
    
    # Сначала пробуем разбить по логическим секциям
    parts = []
    current_part = []
    current_length = 0
    
    for i, line in enumerate(lines):
        line_length = len(line) + 1  # +1 для символа новой строки
        
        # Проверяем, не является ли эта строка разделителем секции
        is_section_break = any(indicator in line for indicator in section_indicators)
        
        # Если текущая часть станет слишком длинной или это разделитель секции
        if (current_length + line_length > max_len and current_part) or (is_section_break and current_part and current_length > max_len * 0.3):
            # Сохраняем текущую часть
            part_text = '\n'.join(current_part).strip()
            if part_text:
                parts.append(part_text)
            
            # Начинаем новую часть
            current_part = [line]
            current_length = line_length
        else:
            # Добавляем строку к текущей части
            current_part.append(line)
            current_length += line_length
    
    # Добавляем последнюю часть
    if current_part:
        part_text = '\n'.join(current_part).strip()
        if part_text:
            parts.append(part_text)
    
    # Если логическое разбиение не сработало или дало слишком много частей, используем стандартное
    if len(parts) == 1 or len(parts) > 10:  # Максимум 10 частей для читаемости
        # Если логическое разбиение дало только 1 часть, но текст длинный, 
        # принудительно разбиваем на несколько частей
        if len(parts) == 1 and len(text) > 1500:
            return _split_into_parts_standard(text, max_len)
        return _split_into_parts_standard(text, max_len)
    
    return parts


def _split_into_parts_standard(text: str, max_len: int = 3000) -> list[str]:
    """Стандартное разбиение текста на части по длине"""
    if len(text) <= max_len:
        # Если текст не превышает max_len, но все равно длинный (>1500), 
        # принудительно разбиваем на 2 части для лучшей читаемости
        if len(text) > 1500:
            mid_point = len(text) // 2
            # Ищем хорошую точку разрыва около середины
            for i in range(mid_point - 100, mid_point + 100):
                if i < 0 or i >= len(text):
                    continue
                if text[i] == '\n':
                    mid_point = i + 1
                    break
                elif text[i] == ' ':
                    mid_point = i + 1
                    break
            
            part1 = text[:mid_point].strip()
            part2 = text[mid_point:].strip()
            
            if part1 and part2:
                return [part1, part2]
        
        return [text]
    
    # Оптимизируем размер частей для лучшей читаемости
    # Если текст очень длинный, разбиваем на более мелкие части
    optimal_part_size = min(max_len, 2500) if len(text) > 4000 else max_len
    
    parts = []
    remaining_text = text
    
    while len(remaining_text) > optimal_part_size:
        # Ищем точку разрыва по абзацам
        split_point = optimal_part_size
        
        # Пытаемся найти хорошую точку разрыва
        for i in range(optimal_part_size - 100, optimal_part_size):  # Ищем в последних 100 символах
            if i < 0:
                break
            if remaining_text[i] == '\n':
                split_point = i + 1
                break
            elif remaining_text[i] == ' ':
                split_point = i + 1
                break
        
        # Разбиваем текст
        part = remaining_text[:split_point].strip()
        parts.append(part)
        
        remaining_text = remaining_text[split_point:].strip()
    
    # Добавляем оставшийся текст
    if remaining_text:
        parts.append(remaining_text)
    
    return parts


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
