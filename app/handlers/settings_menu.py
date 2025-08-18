from __future__ import annotations

from aiogram import Router, types, F
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User
from app.keyboards.common import settings_menu

router = Router()


@router.callback_query(F.data == "menu_settings")
async def open_settings(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        tz = db_user.timezone
    await cb.message.edit_text("Настройки:", reply_markup=settings_menu(tz))
    await cb.answer()


@router.callback_query(F.data.in_({"tz_moscow", "tz_bishkek"}))
async def set_timezone(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    tz = "Europe/Moscow" if cb.data == "tz_moscow" else "Asia/Bishkek"
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        db_user.timezone = tz
    await cb.message.edit_text("Таймзона сохранена ✅", reply_markup=settings_menu(tz))
    await cb.answer("Установлено")






