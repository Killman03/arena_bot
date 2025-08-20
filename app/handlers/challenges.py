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
    end_date = State()


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
    
    ch_items = []
    for c in items:
        end_date_text = f" до {c.end_date.strftime('%d.%m')}" if c.end_date else ""
        ch_items.append((c.id, f"{'🟢' if c.is_active else '🔴'} {c.title} ({c.time_str}){end_date_text}"))
    
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
    
    await state.update_data(time_str=time_str)
    await state.set_state(ChallengeForm.end_date)
    await message.answer("Введите дату окончания челленджа в формате ДД.ММ.ГГГГ (или '-' чтобы без срока):")

@router.message(ChallengeForm.end_date)
async def ch_add_end_date(message: types.Message, state: FSMContext) -> None:
    end_date_str = (message.text or "").strip()
    data = await state.get_data()
    
    # Парсим дату окончания
    end_date = None
    if end_date_str != "-":
        try:
            from datetime import datetime
            end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
            if end_date <= date.today():
                await message.answer("Дата окончания должна быть в будущем. Попробуйте снова:")
                return
        except ValueError:
            await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ или '-' для пропуска:")
            return
    
    user = message.from_user
    if not user:
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        ch = Challenge(
            user_id=db_user.id,
            title=data.get("title", "Без названия"),
            description=data.get("description"),
            time_str=data.get("time_str", "07:00"),
            days_mask="1111110",  # Ежедневно, кроме воскресенья
            end_date=end_date,
        )
        session.add(ch)
    
    await state.clear()
    end_date_text = f" до {end_date.strftime('%d.%m.%Y')}" if end_date else ""
    await message.answer(f"Челлендж создан ✅{end_date_text}", reply_markup=challenges_menu())


@router.callback_query(F.data.startswith("ch_open:"))
async def ch_open(cb: types.CallbackQuery) -> None:
    ch_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        ch = await session.get(Challenge, ch_id)
    if not ch:
        await cb.answer("Не найден")
        return
    
    end_date_text = f"\nДата окончания: {ch.end_date.strftime('%d.%m.%Y')}" if ch.end_date else "\nБез срока окончания"
    text = f"{ch.title}\n{ch.description or ''}\nВремя: {ch.time_str}\nСтатус: {'активен' if ch.is_active else 'выключен'}{end_date_text}"
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
    waiting_end_date = State()


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


@router.callback_query(F.data.startswith("ch_edit_end_date:"))
async def ch_edit_end_date(cb: types.CallbackQuery, state: FSMContext) -> None:
    ch_id = int(cb.data.split(":", 1)[1])
    await state.update_data(ch_id=ch_id)
    await state.set_state(ChallengeEditForm.waiting_end_date)
    await cb.message.edit_text("Введите новую дату окончания в формате ДД.ММ.ГГГГ (или '-' чтобы убрать срок):")
    await cb.answer()


@router.message(ChallengeEditForm.waiting_end_date)
async def ch_edit_end_date_set(message: types.Message, state: FSMContext) -> None:
    end_date_str = (message.text or "").strip()
    data = await state.get_data()
    ch_id = int(data["ch_id"])  # type: ignore[index]
    
    # Парсим дату окончания
    end_date = None
    if end_date_str != "-":
        try:
            from datetime import datetime
            end_date = datetime.strptime(end_date_str, "%d.%m.%Y").date()
            if end_date <= date.today():
                await message.answer("Дата окончания должна быть в будущем. Попробуйте снова:")
                return
        except ValueError:
            await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ или '-' для пропуска:")
            return
    
    async with session_scope() as session:
        ch = await session.get(Challenge, ch_id)
        if ch:
            ch.end_date = end_date
    
    await state.clear()
    end_date_text = f" до {end_date.strftime('%d.%m.%Y')}" if end_date else ""
    await message.answer(f"Дата окончания изменена ✅{end_date_text}", reply_markup=challenges_menu())


@router.callback_query(F.data.startswith("ch_toggle:"))
async def ch_toggle(cb: types.CallbackQuery) -> None:
    ch_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        ch = await session.get(Challenge, ch_id)
        if ch:
            ch.is_active = not ch.is_active
    await cb.answer("Готово")
    await ch_open(cb)


