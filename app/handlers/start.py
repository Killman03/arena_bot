from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User
from app.keyboards.common import main_menu
from app.db.models.motivation import Motivation

router = Router()


PILLARS = [
    "Ответственность",
    "Концепт отложенных перемен",
    "Наличие цели",
    "Осознание главного навыка как мужчины",
    "Система - ключ к достижению цели",
    "Создание характера победителя",
    "Главная определенная цель",
]


@router.message(CommandStart())
async def start_handler(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        existing = await session.execute(select(User).where(User.telegram_id == user.id))
        instance = existing.scalar_one_or_none()
        if not instance:
            instance = User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            session.add(instance)

    main_goal = None
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        if mot and mot.main_year_goal:
            main_goal = mot.main_year_goal
    header = "Добро пожаловать на Гладиаторскую арену жизни!\nЗдесь ты собираешь характер победителя через систему ежедневных практик.\n\n"
    if main_goal:
        header += f"🎯 Главная цель года: {main_goal}\n\n"
    header += "Выбери раздел:"
    await message.answer(header, reply_markup=main_menu())


@router.message(Command("pillars"))
async def pillars_handler(message: types.Message) -> None:
    await message.answer("7 опор:\n- " + "\n- ".join(PILLARS))


@router.message(Command("motivation"))
async def motivation_handler(message: types.Message) -> None:
    from app.services.reminders import LAWS_OF_ARENA
    import random

    principle = random.choice(LAWS_OF_ARENA)
    await message.answer(f"Мотивация дня:\n\n{principle}")


