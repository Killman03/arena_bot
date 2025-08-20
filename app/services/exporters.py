from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    User,
    FinanceTransaction,
)

# Модуль для экспорта финансовых данных пользователя
# Экспортирует: транзакции, кредиторы, должники, доходы


async def export_user_data_to_csv(session: AsyncSession, user_id: int, out_dir: Path) -> dict[str, Path]:
    """Export financial data to CSV files; returns mapping entity -> path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    exports: dict[str, Path] = {}

    async def _dump(query, filename: str) -> Path:
        result = await session.execute(query)
        rows = [row.__dict__ for row in result.scalars().all()]
        for r in rows:
            r.pop("_sa_instance_state", None)
        df = pd.DataFrame(rows)
        path = out_dir / filename
        df.to_csv(path, index=False)
        return path

    # Экспортируем только финансовые данные
    exports["finance"] = await _dump(select(FinanceTransaction).where(FinanceTransaction.user_id == user_id), "finance.csv")
    
    # Добавляем дополнительные финансовые файлы для кредиторов, должников, доходов и финансовых целей
    from app.db.models import Creditor, Debtor, Income, FinancialGoal
    
    exports["creditors"] = await _dump(select(Creditor).where(Creditor.user_id == user_id), "creditors.csv")
    exports["debtors"] = await _dump(select(Debtor).where(Debtor.user_id == user_id), "debtors.csv")
    exports["incomes"] = await _dump(select(Income).where(Income.user_id == user_id), "incomes.csv")
    exports["financial_goals"] = await _dump(select(FinancialGoal).where(FinancialGoal.user_id == user_id), "financial_goals.csv")

    return exports


async def export_user_data_to_excel(session: AsyncSession, user_id: int, out_file: Path) -> Path:
    """Export financial data to a single Excel workbook with multiple sheets."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        async def _sheet(query, sheet: str) -> None:
            result = await session.execute(query)
            rows = [row.__dict__ for row in result.scalars().all()]
            for r in rows:
                r.pop("_sa_instance_state", None)
            pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, index=False)

        # Экспортируем только финансовые данные
        await _sheet(select(FinanceTransaction).where(FinanceTransaction.user_id == user_id), "finance")
        
        # Добавляем дополнительные финансовые листы для кредиторов, должников, доходов и финансовых целей
        from app.db.models import Creditor, Debtor, Income, FinancialGoal
        
        await _sheet(select(Creditor).where(Creditor.user_id == user_id), "creditors")
        await _sheet(select(Debtor).where(Debtor.user_id == user_id), "debtors")
        await _sheet(select(Income).where(Income.user_id == user_id), "incomes")
        await _sheet(select(FinancialGoal).where(FinancialGoal.user_id == user_id), "financial_goals")

    return out_file






