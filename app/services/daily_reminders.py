from __future__ import annotations

from datetime import datetime, time, timedelta, date
from typing import Iterable
import random

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, Motivation, Todo
from app.db.models.goal import Goal, GoalStatus, GoalScope
from app.services.llm import deepseek_complete


LAWS_OF_ARENA: list[str] = [
    "Мне нужен только один идеальный день",
    "Мужчина делает то что должен, несмотря на то, как он себя чувствует",
    "Ясность только в действие",
    "Мужчина не был создан для комфорта",
    "Каждая сложная ситуация это тест на силу характера, которую я разношу, чтобы стать сильнее",
    "Я не жду идеального времени. Я делаю все, что может быть сделано сегодня",
    "Я обречен быть рабом привычек, поэтому я выбираю быть в рабстве привычек, которые меня строят",
    "За все в жизни ответственен только я. Если я хочу что-нибудь изменить я полагаюсь только на свои действия",
    "Время всегда есть до рассвета",
    "Когда вдохновение работать заканчивается, начинается настоящая работа",
    "Процесс важнее цели. Победители держат фокус на ежедневном процессе",
]


def daily_reminder_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ежедневного напоминания с быстрыми действиями"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Добавить задачу на день", callback_data="quick_add_todo"),
                InlineKeyboardButton(text="✨ Один идеальный день", callback_data="perfect_day_plan")
            ],
            [
                InlineKeyboardButton(text="📚 Записать цитату", callback_data="quick_add_quote"),
                InlineKeyboardButton(text="💰 Добавить расход", callback_data="quick_add_expense")
            ],
            [
                InlineKeyboardButton(text="⏰ Создать напоминание", callback_data="quick_add_reminder")
            ]
        ]
    )


def perfect_day_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для планирования идеального дня"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚔️ Создать план", callback_data="create_perfect_day"),
                InlineKeyboardButton(text="📋 Шаблоны дня", callback_data="day_templates")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ]
        ]
    )


async def send_daily_principle(bot: Bot, session: AsyncSession, user_id: int = None) -> None:
    """Отправляет случайный принцип арены пользователям с утренним напоминанием"""
    print(f"📤 send_daily_principle вызвана для user_id: {user_id}")
    
    if user_id:
        # Отправляем конкретному пользователю
        users = [await _get_user_by_id(session, user_id)]
        print(f"🎯 Отправляем конкретному пользователю: {user_id}")
    else:
        # Отправляем всем пользователям (для обратной совместимости)
        users = await _get_all_users(session)
        print(f"🌍 Отправляем всем пользователям: {len(users)}")
    
    if not users:
        print("❌ Нет пользователей для отправки")
        return

    principle = random.choice(LAWS_OF_ARENA)
    print(f"💪 Выбран принцип: {principle}")
    
    for user in users:
        if not user:
            continue
            
        prefs = user.notification_preferences or {}
        if prefs.get("daily_principle", True):
            try:
                print(f"📱 Отправляем сообщение пользователю {user.telegram_id}")
                await bot.send_message(
                    user.telegram_id, 
                    f"🌅 <b>Доброе утро, гладиатор!</b>\n\n"
                    f"💪 <b>Принцип дня:</b>\n{principle}\n\n"
                    f"Готов к новым вызовам?",
                    reply_markup=daily_reminder_keyboard(),
                    parse_mode="HTML"
                )
                print(f"✅ Сообщение отправлено пользователю {user.telegram_id}")
            except Exception as e:
                print(f"❌ Ошибка при отправке пользователю {user.telegram_id}: {e}")
                continue
        else:
            print(f"🔇 Пользователь {user.telegram_id} отключил принципы")


async def send_daily_motivation(bot: Bot, session: AsyncSession, user_id: int = None) -> None:
    """Отправляет мотивационное сообщение с возможностью быстрого добавления задач"""
    if user_id:
        # Отправляем конкретному пользователю
        users = [await _get_user_by_id(session, user_id)]
    else:
        # Отправляем всем пользователям (для обратной совместимости)
        users = await _get_all_users(session)
    
    for user in users:
        if not user:
            continue
            
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == user.id))
        ).scalar_one_or_none()
        if not mot:
            continue
        
        texts = [t for t in [mot.main_year_goal, mot.vision, mot.mission, mot.values] if t]
        if not texts:
            continue
        
        text = random.choice(texts)
        try:
            await bot.send_message(
                user.telegram_id, 
                f"🔥 <b>Мотивация дня:</b>\n\n{text}\n\n"
                f"Что планируешь сделать сегодня для достижения этой цели?",
                reply_markup=daily_reminder_keyboard(),
                parse_mode="HTML"
            )
        except Exception:
            continue


async def generate_perfect_day_plan(user_id: int, session: AsyncSession) -> str:
    """Генерирует план идеального дня с помощью ИИ в стиле гладиаторского ланисты"""
    try:
        # Получаем информацию о пользователе
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        if not user:
            return "Не удалось получить информацию о пользователе."
        
        # Получаем мотивацию пользователя
        motivation = (await session.execute(select(Motivation).where(Motivation.user_id == user_id))).scalar_one_or_none()
        
        # Получаем активные цели пользователя
        goals = (await session.execute(
            select(Goal).where(
                Goal.user_id == user_id,
                Goal.status == GoalStatus.active
            ).order_by(Goal.scope.desc())
        )).scalars().all()
        
        # Получаем задачи на сегодня
        today = date.today()
        today_todos = (await session.execute(
            select(Todo).where(
                Todo.user_id == user_id,
                Todo.due_date == today,
                Todo.is_completed == False
            ).order_by(Todo.priority.desc())
        )).scalars().all()
        
        # Формируем контекст для ИИ
        context_parts = []
        
        # Добавляем мотивацию
        if motivation:
            if motivation.main_year_goal:
                context_parts.append(f"🎯 Главная цель года: {motivation.main_year_goal}")
            if motivation.vision:
                context_parts.append(f"👁️ Видение: {motivation.vision}")
            if motivation.mission:
                context_parts.append(f"⚔️ Миссия: {motivation.mission}")
        
        # Добавляем цели
        if goals:
            context_parts.append("🎯 Активные цели:")
            for goal in goals[:7]:  # Берем первые 5 целей
                scope_text = {
                    GoalScope.five_years: "5 лет",
                    GoalScope.year: "год",
                    GoalScope.month: "месяц",
                    GoalScope.week: "неделя",
                    GoalScope.day: "день"
                }.get(goal.scope, goal.scope)
                context_parts.append(f"  • {goal.title} ({scope_text})")
        
        # Добавляем задачи на сегодня
        if today_todos:
            context_parts.append("📝 Задачи на сегодня:")
            for todo in today_todos[:5]:  # Берем первые 5 задач
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(todo.priority, "⚪")
                context_parts.append(f"  • {priority_emoji} {todo.title}")
        
        context = "\n".join(context_parts) if context_parts else "Нет дополнительного контекста"
        
        # Формируем промпт для ИИ в стиле ланисты
        prompt = f"""Ты - опытный ланиста (тренер гладиаторов), который составляет план тренировок для своего гладиатора. 

Контекст гладиатора:
{context}

Создай детальный план идеального дня в стиле гладиаторских тренировок. Используй воинственную, мотивирующую лексику, но сохраняй практичность.

План должен включать:
1. 🌅 Утреннюю подготовку (5:00-7:00) - работа над главной целью года
2. ⚔️ Основные тренировки (8:00-18:00) - работа над целями и задачами
3. 🛡️ Вечернюю рутину (18:00-20:00) - подведение итогов, восстановление
4. 💪 Время для силы духа - чтение, размышления, развитие

ВАЖНЫЕ ПРАВИЛА:
- НЕ указывай конкретную дату или день недели
- НЕ пиши "на завтра" или "на 22 мая"
- Используй общие формулировки типа "боевой план", "план дня", "устав дня"
- Начни сразу с обращения к гладиатору
- Используй временные рамки (5:00, 8:00 и т.д.)

Формат вывода:
- Используй четкую структуру с временными рамками
- Каждый пункт: время - действие (описание)
- Используй эмодзи для визуального разделения
- Делай текст читаемым и структурированным
- Избегай сложных HTML-тегов

Начни с обращения к гладиатору и закончи мотивирующим призывом к действию."""

        # Генерируем план с помощью ИИ
        plan = await deepseek_complete(prompt, max_tokens=3000)
        
        # Добавляем заголовок в стиле гладиатора
        header = "⚔️ <b>ПРИКАЗ ЛАНИСТЫ ГЛАДИАТОРУ</b>\n\n"
        footer = "\n\n💪 <b>Помни: каждый день - это битва за свою судьбу. Сражайся достойно!</b>"
        
        # Очищаем план от лишних HTML-тегов, которые могут мешать отображению
        import re
        clean_plan = re.sub(r'<[^>]+>', '', plan)  # Убираем HTML-теги
        clean_plan = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', clean_plan)  # Заменяем ** на <b>
        clean_plan = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', clean_plan)  # Заменяем * на <i>
        
        # Убираем упоминания конкретных дат и дней
        clean_plan = re.sub(r'на \d{1,2} [а-яё]+', 'на завтра', clean_plan, flags=re.IGNORECASE)
        clean_plan = re.sub(r'Боевой план на \d{1,2} [а-яё]+', '⚔️ Боевой план', clean_plan, flags=re.IGNORECASE)
        clean_plan = re.sub(r'План на \d{1,2} [а-яё]+', '⚔️ План дня', clean_plan, flags=re.IGNORECASE)
        clean_plan = re.sub(r'Устав на \d{1,2} [а-яё]+', '⚔️ Устав дня', clean_plan, flags=re.IGNORECASE)
        
        # Проверяем длину сообщения (Telegram ограничение ~4096 символов)
        full_message = f"{header}{clean_plan}{footer}"
        if len(full_message) > 4000:
            # Обрезаем план, если он слишком длинный
            max_plan_length = 4000 - len(header) - len(footer) - 50  # Оставляем запас
            clean_plan = clean_plan[:max_plan_length] + "\n\n... (план продолжается)"
        
        return f"{header}{clean_plan}{footer}"
        
    except Exception as e:
        return f"❌ <b>Ошибка при создании плана</b>\n\nНе удалось сгенерировать план: {str(e)}"


async def create_todo_from_perfect_day(user_id: int, plan_text: str, session: AsyncSession) -> bool:
    """Создает задачи в To-Do на основе плана идеального дня"""
    try:
        # Парсим план и создаем задачи
        lines = plan_text.split('\n')
        tasks_created = 0
        
        for line in lines:
            line = line.strip()
            # Ищем строки с временем и действиями (формат: время - действие)
            if line and ('-' in line or ':' in line) and len(line) > 10:
                # Пропускаем заголовки и разделители
                if any(skip in line.lower() for skip in ['приказ', 'ланисты', 'гладиатору', 'помни', 'битва', 'судьба']):
                    continue
                
                # Извлекаем описание задачи
                task_desc = ""
                if '-' in line:
                    parts = line.split('-', 1)
                    if len(parts) > 1:
                        task_desc = parts[1].strip()
                elif ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        task_desc = parts[1].strip()
                
                # Очищаем от эмодзи и лишних символов
                if task_desc:
                    # Убираем эмодзи и лишние пробелы
                    import re
                    task_desc = re.sub(r'[^\w\s\-\.\,\!\?]', '', task_desc).strip()
                    
                    if len(task_desc) > 5:  # Минимальная длина описания
                        # Определяем приоритет на основе времени
                        priority = "medium"
                        if any(time_indicator in line.lower() for time_indicator in ['утро', '6:', '7:', '8:']):
                            priority = "high"  # Утренние дела - высокий приоритет
                        elif any(time_indicator in line.lower() for time_indicator in ['вечер', '20:', '21:', '22:']):
                            priority = "low"  # Вечерние дела - низкий приоритет
                        
                        # Создаем задачу
                        new_todo = Todo(
                            user_id=user_id,
                            title=task_desc[:100],  # Ограничиваем длину
                            description=f"Из плана идеального дня: {line}",
                            due_date=date.today(),
                            priority=priority,
                            is_daily=False
                        )
                        session.add(new_todo)
                        tasks_created += 1
        
        if tasks_created > 0:
            await session.commit()
            return True
        
        return False
        
    except Exception as e:
        print(f"Ошибка при создании задач из плана: {e}")
        return False


async def _get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Получает пользователя по ID"""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _get_all_users(session: AsyncSession) -> list[User]:
    """Получает всех пользователей"""
    result = await session.execute(select(User))
    return list(result.scalars().all())
