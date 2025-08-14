from __future__ import annotations

from aiogram import Router, types, F

from app.keyboards.common import (
    main_menu,
    goals_menu,
    habits_menu,
    finance_menu,
    health_menu,
    nutrition_menu,
    back_main_menu,
    goals_list_keyboard,
)
from sqlalchemy import select
from app.db.session import session_scope
from app.db.models import User, Goal, GoalStatus
from app.services.exporters import export_user_data_to_excel
from pathlib import Path

router = Router()


@router.callback_query(F.data == "back_main")
async def back_main(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Главное меню:", reply_markup=main_menu())
    await cb.answer()


@router.callback_query(F.data == "menu_goals")
async def menu_goals(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Раздел целей:", reply_markup=goals_menu())
    await cb.answer()


@router.callback_query(F.data == "menu_habits")
async def menu_habits(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Раздел привычек:", reply_markup=habits_menu())
    await cb.answer()


HELP_TEXT = (
    "Как работает бот:\n\n"
    "- Меню: выбери раздел — Цели, Привычки, Финансы.\n"
    "- Все сообщения логируются для истории.\n"
    "- ИИ помогает формулировать SMART и мотивировать.\n\n"
    "Команды:\n"
    "/start — приветствие и меню\n"
    "/pillars — 7 опор характера\n"
    "/motivation — мотивационное сообщение\n"
    "/goal_add «текст» — добавить цель (ИИ + Notion)\n"
    "/goals — список активных целей\n"
    "/ab A | B — A/B-анализ с планом шагов\n"
    "/smart scope title | desc | YYYY-MM-DD — SMART-цель\n"
    "/habits_init — создать базовые привычки\n"
    "/habit Название 1.0 [YYYY-MM-DD] — лог привычки (ИИ-отклик)\n"
    "/remind_habit Название HH:MM — персональное напоминание\n"
    "/expense 199.99 Категория описание — записать расход\n"
    "/finance_export — экспорт данных в Excel\n"
    "/meal breakfast Омлет [YYYY-MM-DD] — план питания\n"
    "/pomodoro — старт помодоро 25 минут\n\n"
    "Inline-кнопки:\n"
    "- В меню разделов используйте кнопки навигации.\n"
    "- В целях доступны кнопки завершить/отменить для каждого пункта.\n"
    "- В финансах — экспорт в Excel.\n"
)


@router.callback_query(F.data == "help")
async def help_callback(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text(HELP_TEXT, reply_markup=back_main_menu(), parse_mode=None)
    await cb.answer()


@router.callback_query(F.data == "menu_finance")
async def menu_finance(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Финансы:", reply_markup=finance_menu())
    await cb.answer()


@router.callback_query(F.data == "menu_nutrition")
async def menu_nutrition(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Питание:", reply_markup=nutrition_menu())
    await cb.answer()


@router.callback_query(F.data == "menu_health")
async def menu_health(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Здоровье:", reply_markup=health_menu())
    await cb.answer()


@router.callback_query(F.data == "goals_list")
async def goals_list(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        goals = (
            await session.execute(select(Goal).where(Goal.user_id == db_user.id, Goal.status == GoalStatus.active))
        ).scalars().all()
    items = [(g.id, g.title) for g in goals]
    if not items:
        await cb.message.edit_text("Активных целей нет", reply_markup=goals_menu())
    else:
        await cb.message.edit_text("Ваши цели:", reply_markup=goals_list_keyboard(items))
    await cb.answer()


@router.callback_query(F.data.startswith("goal_done:"))
async def goal_done(cb: types.CallbackQuery) -> None:
    goal_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        goal = await session.get(Goal, goal_id)
        if goal:
            goal.status = GoalStatus.completed
    await cb.answer("Готово ✅")
    await goals_list(cb)


@router.callback_query(F.data.startswith("goal_cancel:"))
async def goal_cancel(cb: types.CallbackQuery) -> None:
    goal_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        goal = await session.get(Goal, goal_id)
        if goal:
            goal.status = GoalStatus.cancelled
    await cb.answer("Отменено ✖")
    await goals_list(cb)


@router.callback_query(F.data == "finance_export_cb")
async def finance_export_cb(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        out = Path("exports") / f"user_{db_user.id}.xlsx"
        await export_user_data_to_excel(session, db_user.id, out)
    try:
        await cb.message.answer_document(types.FSInputFile(out))  # type: ignore[arg-type]
    except Exception:
        await cb.message.answer("Файл экспортирован: " + str(out))
    await cb.answer()


