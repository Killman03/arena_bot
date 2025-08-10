from __future__ import annotations

from datetime import date

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.models import Goal, GoalScope, GoalStatus, ABAnalysis, User
from app.db.session import session_scope
from app.services.llm import deepseek_complete
from app.services.notion import create_goal_page

router = Router()


@router.message(Command("goal_add"))
async def add_goal(message: types.Message) -> None:
    """Add a simple daily goal from text after command."""
    user = message.from_user
    if not user:
        return
    text = (message.text or "").replace("/goal_add", "").strip()
    if not text:
        await message.answer("Использование: /goal_add Ваша цель")
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        goal = Goal(
            user_id=db_user.id,
            scope=GoalScope.day,
            title=text,
            description=None,
            start_date=date.today(),
            status=GoalStatus.active,
        )
        session.add(goal)
    # AI: автогенерация SMART-описания и запись в Notion
    smart_prompt = f"Оцени цель пользователя и оформи SMART-описание кратко: '{text}'. Выведи 5 пунктов: S,M,A,R,T."
    try:
        smart = await deepseek_complete(smart_prompt, system="Ты коуч по целям. Кратко и по делу.")
        notion_id = await create_goal_page({
            "Name": {"title": [{"text": {"content": text}}]},
            "Scope": {"select": {"name": "day"}},
            "SMART": {"rich_text": [{"text": {"content": smart[:1900]}}]},
        })
        await message.answer("Цель добавлена ✅\nSMART:\n" + smart)
    except Exception:
        await message.answer("Цель добавлена ✅")


@router.message(Command("goals"))
async def list_goals(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        goals = (await session.execute(select(Goal).where(Goal.user_id == db_user.id, Goal.status == GoalStatus.active))).scalars().all()
    if not goals:
        await message.answer("Активных целей нет")
        return
    lines = [f"[{g.scope}] {g.title}" for g in goals]
    await message.answer("Ваши цели:\n- " + "\n- ".join(lines))


@router.message(Command("ab"))
async def ab_analysis(message: types.Message) -> None:
    """Store quick A/B analysis: /ab сейчас | хочу."""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/ab", "", 1).strip()
    if "|" not in payload:
        await message.answer("Использование: /ab где_я_сейчас | где_хочу_быть")
        return
    current, desired = [p.strip() for p in payload.split("|", 1)]
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        session.add(ABAnalysis(user_id=db_user.id, current_state=current, desired_state=desired))
    # AI: краткий план действий
    try:
        plan = await deepseek_complete(
            f"Сформируй краткий пошаговый план перехода из состояния A='{current}' в B='{desired}'. Дай 5 шагов.",
            system="Кратко, по делу, без воды.",
        )
        await message.answer("A/B анализ сохранен ✅\nПлан:\n" + plan)
    except Exception:
        await message.answer("A/B анализ сохранен ✅")


@router.message(Command("smart"))
async def smart_goal(message: types.Message) -> None:
    """Создать SMART-цель: /smart scope title | description | due_date(YYYY-MM-DD)"""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/smart", "", 1).strip()
    if payload.count("|") < 1:
        await message.answer("Пример: /smart 1m Пробежать 10км | Тренировки 3р/нед | 2025-10-01")
        return
    head, rest = payload.split(" ", 1)
    scope_map = {"5y": GoalScope.five_years, "1y": GoalScope.year, "1m": GoalScope.month, "1d": GoalScope.day}
    scope = scope_map.get(head, GoalScope.month)
    title, desc, *maybe_due = [p.strip() for p in rest.split("|")]
    due = date.fromisoformat(maybe_due[0]) if maybe_due else None
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        g = Goal(user_id=db_user.id, scope=scope, title=title, description=desc or None, start_date=date.today(), due_date=due)
        session.add(g)
    # AI: SMART-валидация
    try:
        smart_feedback = await deepseek_complete(
            f"Проверь SMART цель: title='{title}', desc='{desc}', due='{due}'. Дай улучшения в 3-5 пунктах.",
            system="Эксперт SMART",
        )
        await message.answer("SMART цель добавлена ✅\nРекомендации:\n" + smart_feedback)
    except Exception:
        await message.answer("SMART цель добавлена ✅")


