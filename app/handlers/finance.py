from __future__ import annotations

from datetime import datetime

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.models import FinanceTransaction, User
from app.db.session import session_scope

router = Router()


@router.message(Command("expense"))
async def add_expense(message: types.Message) -> None:
    """Quick expense: /expense 199.99 Категория описание..."""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/expense", "", 1).strip()
    if not payload:
        await message.answer("Использование: /expense 199.99 Категория описание")
        return
    parts = payload.split()
    amount = float(parts[0])
    category = parts[1] if len(parts) > 1 else "Прочее"
    description = " ".join(parts[2:]) if len(parts) > 2 else None

    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        session.add(
            FinanceTransaction(
                user_id=db_user.id,
                date=datetime.utcnow().date(),
                amount=amount,
                category=category,
                description=description,
            )
        )
    await message.answer("Расход записан ✅")


@router.message(Command("finance_export"))
async def finance_export(message: types.Message) -> None:
    """Экспорт финансов и другой статистики в Excel: /finance_export"""
    user = message.from_user
    if not user:
        return
    from pathlib import Path
    from app.services.exporters import export_user_data_to_excel

    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        out = Path("exports") / f"user_{db_user.id}.xlsx"
        await export_user_data_to_excel(session, db_user.id, out)

    await message.answer("Экспортирован файл по пути: exports/user_#.xlsx (локально)")


