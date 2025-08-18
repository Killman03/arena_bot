from __future__ import annotations

import csv
from io import StringIO
from datetime import datetime

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import FinanceTransaction, User

router = Router()


@router.message(Command("finance_upload"))
async def finance_upload(message: types.Message) -> None:
    """Отправьте CSV-файл как ответ на это сообщение. Ожидаемые колонки: date,amount,category,description"""
    await message.answer("Пришлите CSV-файл банковской выписки ответом на это сообщение.")


@router.message(lambda m: m.document and (m.caption or "").startswith("#finance"))
async def handle_bank_csv(message: types.Message, bot: types.Bot) -> None:  # type: ignore[override]
    """Парсит CSV, импортирует транзакции. Используйте caption: #finance"""
    user = message.from_user
    if not user:
        return
    file = await bot.get_file(message.document.file_id)  # type: ignore[attr-defined]
    content = await bot.download_file(file.file_path)  # type: ignore[arg-type]
    text = content.read().decode("utf-8")
    reader = csv.DictReader(StringIO(text))
    rows = list(reader)
    count = 0
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        for r in rows:
            try:
                dt = datetime.fromisoformat(r["date"]).date()
                amount = float(r["amount"])
                category = r.get("category", "Прочее") or "Прочее"
                description = r.get("description")
            except Exception:
                continue
            session.add(
                FinanceTransaction(
                    user_id=db_user.id,
                    date=dt,
                    amount=amount,
                    category=category,
                    description=description,
                )
            )
            count += 1
    await message.answer(f"Импортировано записей: {count}")






