from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransaction


async def export_monthly_analytics_excel(session: AsyncSession, user_id: int, year: int, month: int, out_file: Path) -> Path:
    """Build a simple monthly analytics Excel with category aggregations."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    result = await session.execute(
        select(FinanceTransaction).where(
            FinanceTransaction.user_id == user_id,
            FinanceTransaction.date >= start,
            FinanceTransaction.date < end,
        )
    )
    rows = [
        {
            "date": r.date,
            "amount": float(r.amount),
            "category": r.category,
            "description": r.description,
        }
        for r in result.scalars().all()
    ]
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="raw", index=False)
        if not df.empty:
            pivot = df.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
            pivot.to_excel(writer, sheet_name="by_category", index=False)
    return out_file



