from __future__ import annotations

from datetime import date

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User, Challenge, ChallengeLog
from app.keyboards.common import (
    challenges_menu,
    challenges_list_keyboard,
    challenge_detail_keyboard,
    back_main_menu,
)

router = Router()


class ChallengeForm(StatesGroup):
    title = State()
    description = State()
    time_str = State()


@router.callback_query(F.data == "menu_challenges")
async def menu_challenges(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Челленджи:", reply_markup=challenges_menu())
    await cb.answer()


@router.callback_query(F.data == "ch_list")
async def ch_list(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        items = (
            await session.execute(select(Challenge).where(Challenge.user_id == db_user.id))
        ).scalars().all()
    ch_items = [(c.id, f"{'🟢' if c.is_active else '🔴'} {c.title} ({c.time_str})") for c in items]
    await cb.message.edit_text("Ваши челленджи:", reply_markup=challenges_list_keyboard(ch_items))
    await cb.answer()


@router.callback_query(F.data == "ch_add")
async def ch_add(cb: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChallengeForm.title)
    await cb.message.edit_text("Введите название челленджа:", reply_markup=back_main_menu())
    await cb.answer()


@router.message(ChallengeForm.title)
async def ch_add_title(message: types.Message, state: FSMContext) -> None:
    await state.update_data(title=(message.text or "").strip())
    await state.set_state(ChallengeForm.description)
    await message.answer("Введите описание (или '-' чтобы пропустить):")


@router.message(ChallengeForm.description)
async def ch_add_desc(message: types.Message, state: FSMContext) -> None:
    desc = (message.text or "").strip()
    await state.update_data(description=None if desc == "-" else desc)
    await state.set_state(ChallengeForm.time_str)
    await message.answer("Введите время в формате HH:MM (например, 07:00):")


@router.message(ChallengeForm.time_str)
async def ch_add_time(message: types.Message, state: FSMContext) -> None:
    time_str = (message.text or "").strip()
    # простая валидация
    if len(time_str) != 5 or time_str[2] != ":":
        await message.answer("Неверный формат, используйте HH:MM. Попробуйте снова:")
        return
    data = await state.get_data()
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        ch = Challenge(
            user_id=db_user.id,
            title=data.get("title", "Без названия"),
            description=data.get("description"),
            time_str=time_str,
            days_mask="1111110",  # Ежедневно, кроме воскресенья
        )
        session.add(ch)
    await state.clear()
    await message.answer("Челлендж создан ✅", reply_markup=challenges_menu())


@router.callback_query(F.data.startswith("ch_open:"))
async def ch_open(cb: types.CallbackQuery) -> None:
    ch_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        ch = await session.get(Challenge, ch_id)
    if not ch:
        await cb.answer("Не найден")
        return
    text = f"{ch.title}\n{ch.description or ''}\nВремя: {ch.time_str}\nСтатус: {'активен' if ch.is_active else 'выключен'}"
    await cb.message.edit_text(text, reply_markup=challenge_detail_keyboard(ch_id))
    await cb.answer()


@router.callback_query(F.data.startswith("ch_done:"))
async def ch_done(cb: types.CallbackQuery) -> None:
    ch_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        ch = await session.get(Challenge, ch_id)
        if ch:
            session.add(ChallengeLog(challenge_id=ch_id, date=date.today(), completed=True))
    await cb.answer("Отмечено ✅")
    await ch_open(cb)


class ChallengeTimeForm(StatesGroup):
    waiting_time = State()


@router.callback_query(F.data.startswith("ch_time:"))
async def ch_time(cb: types.CallbackQuery, state: FSMContext) -> None:
    ch_id = int(cb.data.split(":", 1)[1])
    await state.update_data(ch_id=ch_id)
    await state.set_state(ChallengeTimeForm.waiting_time)
    await cb.message.edit_text("Введите новое время HH:MM:")
    await cb.answer()


@router.message(ChallengeTimeForm.waiting_time)
async def ch_time_set(message: types.Message, state: FSMContext) -> None:
    t = (message.text or "").strip()
    data = await state.get_data()
    ch_id = int(data["ch_id"])  # type: ignore[index]
    if len(t) != 5 or t[2] != ":":
        await message.answer("Неверный формат, используйте HH:MM")
        return
    async with session_scope() as session:
        ch = await session.get(Challenge, ch_id)
        if ch:
            ch.time_str = t
    await state.clear()
    await message.answer("Время обновлено ✅", reply_markup=challenges_menu())


class ChallengeEditForm(StatesGroup):
    waiting_text = State()


@router.callback_query(F.data.startswith("ch_edit:"))
async def ch_edit(cb: types.CallbackQuery, state: FSMContext) -> None:
    ch_id = int(cb.data.split(":", 1)[1])
    await state.update_data(ch_id=ch_id)
    await state.set_state(ChallengeEditForm.waiting_text)
    await cb.message.edit_text("Пришлите новый текст челленджа:")
    await cb.answer()


@router.message(ChallengeEditForm.waiting_text)
async def ch_edit_set(message: types.Message, state: FSMContext) -> None:
    txt = (message.text or "").strip()
    data = await state.get_data()
    ch_id = int(data["ch_id"])  # type: ignore[index]
    async with session_scope() as session:
        ch = await session.get(Challenge, ch_id)
        if ch:
            ch.title = txt
    await state.clear()
    await message.answer("Изменено ✅", reply_markup=challenges_menu())


@router.callback_query(F.data.startswith("ch_toggle:"))
async def ch_toggle(cb: types.CallbackQuery) -> None:
    ch_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        ch = await session.get(Challenge, ch_id)
        if ch:
            ch.is_active = not ch.is_active
    await cb.answer("Готово")
    await ch_open(cb)


