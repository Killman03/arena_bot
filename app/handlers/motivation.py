from __future__ import annotations

from datetime import datetime

from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User, Motivation
from app.keyboards.common import motivation_menu, back_main_menu, motivation_edit_menu
from app.services.llm import deepseek_complete

router = Router()


async def _get_or_create_motivation(user_id: int) -> Motivation:
    async with session_scope() as session:
        m = (
            await session.execute(select(Motivation).where(Motivation.user_id == user_id))
        ).scalar_one_or_none()
        if m is None:
            m = Motivation(user_id=user_id, year=datetime.utcnow().year)
            session.add(m)
        return m


@router.callback_query(F.data == "menu_motivation")
async def menu_motivation(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        main_goal = mot.main_year_goal if mot and mot.main_year_goal else "(не задана)"
    await cb.message.edit_text(f"🔥 Мотивация\nГлавная цель года: {main_goal}", reply_markup=motivation_menu())
    await cb.answer()
@router.callback_query(F.data == "mot_edit")
async def mot_edit(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Что изменить?", reply_markup=motivation_edit_menu())
    await cb.answer()


@router.callback_query(F.data == "mot_edit_vision")
async def mot_edit_vision(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Пришлите текст новой версии видения командой: /set_vision текст", reply_markup=back_main_menu())
    await cb.answer()


@router.callback_query(F.data == "mot_edit_mission")
async def mot_edit_mission(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Пришлите команду: /set_mission текст", reply_markup=back_main_menu())
    await cb.answer()


@router.callback_query(F.data == "mot_edit_values")
async def mot_edit_values(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Пришлите команду: /set_values значение1, значение2, ...", reply_markup=back_main_menu())
    await cb.answer()


@router.callback_query(F.data == "mot_edit_year_goal")
async def mot_edit_year_goal(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Пришлите команду: /set_year_goal 2025 | главная цель", reply_markup=back_main_menu())
    await cb.answer()


@router.callback_query(F.data == "mot_view")
async def mot_view(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
    text = (
        f"👁 Видение: {mot.vision if mot and mot.vision else '(не задано)'}\n\n"
        f"🧭 Миссия: {mot.mission if mot and mot.mission else '(не задано)'}\n\n"
        f"💎 Ценности: {mot.values if mot and mot.values else '(не задано)'}\n\n"
        f"🎯 Главная цель {mot.year if mot and mot.year else ''}: {mot.main_year_goal if mot and mot.main_year_goal else '(не задана)'}"
    )
    await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode=None)
    await cb.answer()


@router.callback_query(F.data == "mot_year_goal")
async def mot_year_goal(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
    text = (
        f"🎯 Главная цель {mot.year if mot and mot.year else ''}:\n\n{mot.main_year_goal}"
        if mot and mot.main_year_goal else "Главная цель еще не задана. Используйте: /set_year_goal 2025 | цель"
    )
    await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode=None)
    await cb.answer()


@router.callback_query(F.data == "mot_mission")
async def mot_mission(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
    text = mot.mission if mot and mot.mission else "Миссия еще не задана. Используйте: /set_mission текст"
    await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode=None)
    await cb.answer()


@router.callback_query(F.data == "mot_values")
async def mot_values(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
    text = mot.values if mot and mot.values else "Ценности еще не заданы. Используйте: /set_values значение1, значение2, ..."
    await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode=None)
    await cb.answer()

@router.message(Command("set_vision"))
async def set_vision(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    vision = (message.text or "").replace("/set_vision", "", 1).strip()
    if not vision:
        await message.answer("Использование: /set_vision текст")
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        if mot is None:
            mot = Motivation(user_id=db_user.id, year=datetime.utcnow().year)
            session.add(mot)
        mot.vision = vision
    status_msg = await message.answer("⏳ Генерирую подсказку по видению...")
    try:
        hint = await deepseek_complete(f"Улучшить и усилить видение: {vision}")
        await status_msg.edit_text("Видение сохранено ✅\nПодсказка ИИ:\n" + hint)
    except Exception:
        await status_msg.edit_text("Видение сохранено ✅")


@router.message(Command("set_mission"))
async def set_mission(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    mission = (message.text or "").replace("/set_mission", "", 1).strip()
    if not mission:
        await message.answer("Использование: /set_mission текст")
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        if mot is None:
            mot = Motivation(user_id=db_user.id, year=datetime.utcnow().year)
            session.add(mot)
        mot.mission = mission
    status_msg = await message.answer("⏳ Генерирую подсказку по миссии...")
    try:
        hint = await deepseek_complete(f"Улучшить миссию: {mission}")
        await status_msg.edit_text("Миссия сохранена ✅\nПодсказка ИИ:\n" + hint)
    except Exception:
        await status_msg.edit_text("Миссия сохранена ✅")


@router.message(Command("set_values"))
async def set_values(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    values = (message.text or "").replace("/set_values", "", 1).strip()
    if not values:
        await message.answer("Использование: /set_values список через запятую")
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        if mot is None:
            mot = Motivation(user_id=db_user.id, year=datetime.utcnow().year)
            session.add(mot)
        mot.values = values
    await message.answer("Ценности сохранены ✅")


@router.message(Command("set_year_goal"))
async def set_year_goal(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/set_year_goal", "", 1).strip()
    if "|" not in payload:
        await message.answer("Использование: /set_year_goal 2025 | главная цель")
        return
    year_str, goal = [p.strip() for p in payload.split("|", 1)]
    year = int(year_str)
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        if mot is None:
            mot = Motivation(user_id=db_user.id, year=year)
            session.add(mot)
        mot.year = year
        mot.main_year_goal = goal
    await message.answer("Главная цель года сохранена ✅")


