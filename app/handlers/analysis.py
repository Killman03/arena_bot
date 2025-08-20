from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.session import session_scope
from app.db.models import User, WeeklyRetro, Goal, FinanceTransaction, Challenge, ChallengeLog
from app.keyboards.common import analysis_menu, back_main_menu
from app.services.llm import deepseek_complete

router = Router()


def _split_into_messages(text: str, max_len: int = 3000) -> list[str]:
    """Разбить текст на несколько сообщений для лучшей читаемости"""
    if not text:
        return []
    
    # Если текст короткий, не разбиваем
    if len(text) <= max_len:
        return [text]
    
    # Если текст очень длинный (>4000), разбиваем на 3 части
    if len(text) > 4000:
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


class AnalysisStates(StatesGroup):
    """Состояния для FSM анализа недели."""
    waiting_for_success = State()
    waiting_for_success_reason = State()
    waiting_for_failure = State()
    waiting_for_failure_reason = State()


@router.callback_query(F.data == "menu_analysis")
async def analysis_menu_handler(callback: types.CallbackQuery) -> None:
    """Показать меню анализа."""
    await callback.message.edit_text(
        "📊 **Еженедельный анализ**\n\n"
        "Здесь ты можешь провести глубокий анализ прошедшей недели "
        "и получить персональные рекомендации от ИИ на основе твоих данных.",
        reply_markup=analysis_menu()
    )


@router.callback_query(F.data == "analysis_start")
async def start_analysis_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    """Начать процесс анализа недели."""
    await state.set_state(AnalysisStates.waiting_for_success)
    await callback.message.edit_text(
        "📝 **Анализ недели**\n\n"
        "Давайте разберем прошедшую неделю по шагам.\n\n"
        "**Шаг 1/4:** Что получилось на этой неделе?\n"
        "Опиши свои достижения, успехи и положительные моменты:",
        reply_markup=back_main_menu()
    )


@router.message(AnalysisStates.waiting_for_success)
async def process_success_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать ответ о том, что получилось."""
    await state.update_data(success=message.text)
    await state.set_state(AnalysisStates.waiting_for_success_reason)
    await message.answer(
        "**Шаг 2/4:** Почему это получилось?\n"
        "Объясни причины успеха, что помогло достичь этих результатов:"
    )


@router.message(AnalysisStates.waiting_for_success_reason)
async def process_success_reason_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать ответ о причинах успеха."""
    await state.update_data(success_reason=message.text)
    await state.set_state(AnalysisStates.waiting_for_failure)
    await message.answer(
        "**Шаг 3/4:** Что не получилось на этой неделе?\n"
        "Опиши неудачи, проблемы и то, что не удалось реализовать:"
    )


@router.message(AnalysisStates.waiting_for_failure)
async def process_failure_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать ответ о том, что не получилось."""
    await state.update_data(failure=message.text)
    await state.set_state(AnalysisStates.waiting_for_failure_reason)
    await message.answer(
        "**Шаг 4/4:** Почему это не получилось?\n"
        "Проанализируй причины неудач, что помешало достичь целей:"
    )


@router.message(AnalysisStates.waiting_for_failure_reason)
async def process_failure_reason_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать ответ о причинах неудач и завершить анализ."""
    await state.update_data(failure_reason=message.text)
    
    # Получить все данные из состояния
    data = await state.get_data()
    
    # Сохранить анализ в базу данных
    user = message.from_user
    if not user:
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(
            select(User).where(User.telegram_id == user.id)
        )).scalar_one()
        
        # Определить начало недели (понедельник)
        today = datetime.now()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Создать запись анализа
        analysis = WeeklyRetro(
            user_id=db_user.id,
            week_start=week_start,
            did_well=data.get("success"),
            why_good=data.get("success_reason"),
            not_well=data.get("failure"),
            why_bad=data.get("failure_reason")
        )
        session.add(analysis)
        await session.commit()
        
        # Получить последние 10 записей для анализа ИИ
        recent_data = await get_recent_user_data(session, db_user.id)
        
        # Сгенерировать анализ с помощью ИИ
        try:
            await message.answer("⏳ **Генерирую рекомендации ИИ...**", parse_mode="Markdown")
        except Exception:
            pass
        ai_analysis = await generate_ai_analysis(data, recent_data)
        
        # Обновить запись с планом от ИИ
        analysis.plan = ai_analysis
        await session.commit()
    
    # Очистить состояние
    await state.clear()
    
    # Отправить результат
    await message.answer(
        f"✅ **Анализ недели завершен!**\n\n"
        f"📊 **Ваши ответы:**\n"
        f"✅ **Что получилось:** {data.get('success')}\n"
        f"💡 **Почему получилось:** {data.get('success_reason')}\n"
        f"❌ **Что не получилось:** {data.get('failure')}\n"
        f"🤔 **Почему не получилось:** {data.get('failure_reason')}",
        reply_markup=back_main_menu(),
        parse_mode="Markdown"
    )
    
    # Отправить рекомендации ИИ отдельными сообщениями
    if ai_analysis:
        await message.answer("🤖 **Рекомендации ИИ:**", parse_mode="Markdown")
        parts = _split_into_messages(ai_analysis)
        for i, part in enumerate(parts, 1):
            if i == 1:
                await message.answer(part, parse_mode="Markdown")
            else:
                await message.answer(f"**Продолжение рекомендаций:**\n{part}", parse_mode="Markdown")


@router.callback_query(F.data == "analysis_history")
async def analysis_history_handler(callback: types.CallbackQuery) -> None:
    """Показать историю анализов."""
    user = callback.from_user
    if not user:
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(
            select(User).where(User.telegram_id == user.id)
        )).scalar_one()
        
        # Получить последние 5 анализов
        analyses = (await session.execute(
            select(WeeklyRetro)
            .where(WeeklyRetro.user_id == db_user.id)
            .order_by(desc(WeeklyRetro.week_start))
            .limit(5)
        )).scalars().all()
    
    if not analyses:
        await callback.message.edit_text(
            "📊 **История анализов**\n\n"
            "У вас пока нет сохраненных анализов. "
            "Начните свой первый анализ недели!",
            reply_markup=back_main_menu()
        )
        return
    
    history_text = "📊 **История анализов**\n\n"
    for i, analysis in enumerate(analyses, 1):
        week_end = analysis.week_start + timedelta(days=6)
        history_text += f"**{i}. Неделя {analysis.week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}**\n"
        
        if analysis.did_well:
            history_text += f"✅ **Успехи:** {analysis.did_well[:100]}{'...' if len(analysis.did_well) > 100 else ''}\n"
        
        if analysis.not_well:
            history_text += f"❌ **Неудачи:** {analysis.not_well[:100]}{'...' if len(analysis.not_well) > 100 else ''}\n"
        
        history_text += "\n"
    
    await callback.message.edit_text(
        history_text,
        reply_markup=back_main_menu()
    )


async def get_recent_user_data(session, user_id: int) -> dict[str, Any]:
    """Получить последние 10 записей пользователя для анализа."""
    recent_data = {
        "goals": [],
        "finances": [],
        "challenges": []
    }
    
    # Последние цели
    goals = (await session.execute(
        select(Goal)
        .where(Goal.user_id == user_id)
        .order_by(desc(Goal.created_at))
        .limit(10)
    )).scalars().all()
    recent_data["goals"] = [{"title": g.title, "description": g.description, "status": g.status.value} for g in goals]
    
    # Последние финансовые транзакции
    finances = (await session.execute(
        select(FinanceTransaction)
        .where(FinanceTransaction.user_id == user_id)
        .order_by(desc(FinanceTransaction.created_at))
        .limit(10)
    )).scalars().all()
    recent_data["finances"] = [{"amount": f.amount, "category": f.category, "description": f.description} for f in finances]
    
    # Последние логи челленджей
    challenge_logs = (await session.execute(
        select(ChallengeLog)
        .join(Challenge, ChallengeLog.challenge_id == Challenge.id)
        .where(Challenge.user_id == user_id)
        .order_by(desc(ChallengeLog.created_at))
        .limit(10)
    )).scalars().all()
    recent_data["challenges"] = [{"completed": c.completed, "note": c.note} for c in challenge_logs]
    
    return recent_data


async def generate_ai_analysis(analysis_data: dict, recent_data: dict) -> str:
    """Генерировать анализ с помощью ИИ на основе данных пользователя."""
    
    # Подготовить контекст для ИИ
    context = f"""
Анализ недели пользователя:

Что получилось: {analysis_data.get('success', 'Не указано')}
Почему получилось: {analysis_data.get('success_reason', 'Не указано')}
Что не получилось: {analysis_data.get('failure', 'Не указано')}
Почему не получилось: {analysis_data.get('failure_reason', 'Не указано')}

Последние данные пользователя:
- Цели: {len(recent_data['goals'])} записей
- Финансы: {len(recent_data['finances'])} записей
- Челленджи: {len(recent_data['challenges'])} записей

Детали последних записей:
Цели: {recent_data['goals']}
Финансы: {recent_data['finances']}
Челленджи: {recent_data['challenges']}
"""
    
    system_prompt = """Ты - персональный коуч и аналитик. Проанализируй данные пользователя и дай конкретные, практические рекомендации для улучшения его результатов на следующей неделе. 

Фокус на:
1. Конкретные действия для улучшения
2. Работа с препятствиями
3. Усиление успешных паттернов
4. Практические советы по продуктивности

Будь мотивирующим, но реалистичным. Дай 3-5 конкретных рекомендаций."""
    
    try:
        ai_response = await deepseek_complete(
            prompt=f"Проанализируй эти данные и дай рекомендации:\n\n{context}",
            system=system_prompt,
            max_tokens=5000
        )
        return ai_response
    except Exception as e:
        return f"К сожалению, не удалось сгенерировать анализ ИИ. Ошибка: {str(e)}"
