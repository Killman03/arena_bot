from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import pandas as pd
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    FinanceTransaction,
    Creditor,
    Debtor,
    Income,
    User
)


class ExcelImporter:
    """Класс для импорта Excel файлов и обновления данных в базе"""
    
    def __init__(self, session: AsyncSession, user_id: int):
        self.session = session
        self.user_id = user_id
        self.results = {
            "updated": 0,
            "created": 0,
            "deleted": 0,
            "errors": []
        }
        # Храним ID из Excel для сравнения с базой
        self.excel_ids = {
            "finance": set(),
            "creditors": set(),
            "debtors": set(),
            "incomes": set()
        }
        # Храним существующие ID из базы
        self.existing_ids = {
            "finance": set(),
            "creditors": set(),
            "debtors": set(),
            "incomes": set()
        }
    
    async def import_excel_file(self, excel_path: Path) -> Dict[str, Any]:
        """Импортировать Excel файл и обновить данные в базе"""
        try:
            # Читаем Excel файл
            excel_data = pd.read_excel(excel_path, sheet_name=None)
            
            # Получаем текущие ID из базы для сравнения
            await self._get_existing_ids()
            
            # Обрабатываем каждый лист
            if "finance" in excel_data:
                await self._process_finance_sheet(excel_data["finance"])
            
            if "creditors" in excel_data:
                await self._process_creditors_sheet(excel_data["creditors"])
            
            if "debtors" in excel_data:
                await self._process_debtors_sheet(excel_data["debtors"])
            
            if "incomes" in excel_data:
                await self._process_incomes_sheet(excel_data["incomes"])
            
            # Удаляем записи, которых нет в Excel
            await self._cleanup_deleted_records()
            
            # Сохраняем изменения
            await self.session.commit()
            
            return self.results
            
        except Exception as e:
            self.results["errors"].append(f"Ошибка импорта: {str(e)}")
            return self.results
    
    async def _process_finance_sheet(self, df: pd.DataFrame) -> None:
        """Обработать лист с финансовыми транзакциями"""
        if df.empty:
            return
        
        # Добавляем недостающие колонки если их нет
        if "id" not in df.columns:
            df["id"] = None
        
        for index, row in df.iterrows():
            try:
                transaction_id = row.get("id")
                
                if pd.isna(transaction_id) or transaction_id is None:
                    # Создаем новую транзакцию
                    await self._create_finance_transaction(row)
                else:
                    # Обновляем существующую транзакцию
                    await self._update_finance_transaction(int(transaction_id), row)
                    # Добавляем ID в множество для сравнения
                    self.excel_ids["finance"].add(int(transaction_id))
                    
            except Exception as e:
                self.results["errors"].append(f"Строка {index + 2}: {str(e)}")
    
    async def _create_finance_transaction(self, row: pd.Series) -> None:
        """Создать новую финансовую транзакцию"""
        try:
            # Парсим дату
            transaction_date = self._parse_date(row.get("date"))
            if not transaction_date:
                raise ValueError("Неверный формат даты")
            
            # Парсим сумму
            amount = float(row.get("amount", 0))
            if amount == 0:
                raise ValueError("Сумма не может быть нулевой")
            
            # Создаем транзакцию
            transaction = FinanceTransaction(
                user_id=self.user_id,
                date=transaction_date,
                amount=amount,
                category=str(row.get("category", "Прочее")),
                description=str(row.get("description", ""))
            )
            
            self.session.add(transaction)
            self.results["created"] += 1
            
        except Exception as e:
            raise ValueError(f"Ошибка создания транзакции: {str(e)}")
    
    async def _update_finance_transaction(self, transaction_id: int, row: pd.Series) -> None:
        """Обновить существующую финансовую транзакцию"""
        try:
            # Проверяем существование транзакции
            transaction = await self.session.get(FinanceTransaction, transaction_id)
            if not transaction or transaction.user_id != self.user_id:
                raise ValueError("Транзакция не найдена")
            
            # Парсим дату
            transaction_date = self._parse_date(row.get("date"))
            if not transaction_date:
                raise ValueError("Неверный формат даты")
            
            # Парсим сумму
            amount = float(row.get("amount", 0))
            if amount == 0:
                raise ValueError("Сумма не может быть нулевой")
            
            # Обновляем данные
            transaction.date = transaction_date
            transaction.amount = amount
            transaction.category = str(row.get("category", "Прочее"))
            transaction.description = str(row.get("description", ""))
            
            self.results["updated"] += 1
            
        except Exception as e:
            raise ValueError(f"Ошибка обновления транзакции: {str(e)}")
    
    async def _process_creditors_sheet(self, df: pd.DataFrame) -> None:
        """Обработать лист с кредиторами"""
        if df.empty:
            return
        
        if "id" not in df.columns:
            df["id"] = None
        
        for index, row in df.iterrows():
            try:
                creditor_id = row.get("id")
                
                if pd.isna(creditor_id) or creditor_id is None:
                    await self._create_creditor(row)
                else:
                    await self._update_creditor(int(creditor_id), row)
                    # Добавляем ID в множество для сравнения
                    self.excel_ids["creditors"].add(int(creditor_id))
                    
            except Exception as e:
                self.results["errors"].append(f"Кредитор строка {index + 2}: {str(e)}")
    
    async def _create_creditor(self, row: pd.Series) -> None:
        """Создать нового кредитора"""
        try:
            due_date = self._parse_date(row.get("due_date"))
            if not due_date:
                raise ValueError("Неверный формат даты выплаты")
            
            creditor = Creditor(
                user_id=self.user_id,
                name=str(row.get("name", "")),
                amount=float(row.get("amount", 0)),
                due_date=due_date,
                description=str(row.get("description", "")),
                is_active=True
            )
            
            self.session.add(creditor)
            self.results["created"] += 1
            
        except Exception as e:
            raise ValueError(f"Ошибка создания кредитора: {str(e)}")
    
    async def _update_creditor(self, creditor_id: int, row: pd.Series) -> None:
        """Обновить существующего кредитора"""
        try:
            creditor = await self.session.get(Creditor, creditor_id)
            if not creditor or creditor.user_id != self.user_id:
                raise ValueError("Кредитор не найден")
            
            due_date = self._parse_date(row.get("due_date"))
            if not due_date:
                raise ValueError("Неверный формат даты выплаты")
            
            creditor.name = str(row.get("name", ""))
            creditor.amount = float(row.get("amount", 0))
            creditor.due_date = due_date
            creditor.description = str(row.get("description", ""))
            
            self.results["updated"] += 1
            
        except Exception as e:
            raise ValueError(f"Ошибка обновления кредитора: {str(e)}")
    
    async def _process_debtors_sheet(self, df: pd.DataFrame) -> None:
        """Обработать лист с должниками"""
        if df.empty:
            return
        
        if "id" not in df.columns:
            df["id"] = None
        
        for index, row in df.iterrows():
            try:
                debtor_id = row.get("id")
                
                if pd.isna(debtor_id) or debtor_id is None:
                    await self._create_debtor(row)
                else:
                    await self._update_debtor(int(debtor_id), row)
                    # Добавляем ID в множество для сравнения
                    self.excel_ids["debtors"].add(int(debtor_id))
                    
            except Exception as e:
                self.results["errors"].append(f"Должник строка {index + 2}: {str(e)}")
    
    async def _create_debtor(self, row: pd.Series) -> None:
        """Создать нового должника"""
        try:
            due_date = self._parse_date(row.get("due_date"))
            if not due_date:
                raise ValueError("Неверный формат даты выплаты")
            
            debtor = Debtor(
                user_id=self.user_id,
                name=str(row.get("name", "")),
                amount=float(row.get("amount", 0)),
                due_date=due_date,
                description=str(row.get("description", "")),
                is_active=True
            )
            
            self.session.add(debtor)
            self.results["created"] += 1
            
        except Exception as e:
            raise ValueError(f"Ошибка создания должника: {str(e)}")
    
    async def _update_debtor(self, debtor_id: int, row: pd.Series) -> None:
        """Обновить существующего должника"""
        try:
            debtor = await self.session.get(Debtor, debtor_id)
            if not debtor or debtor.user_id != self.user_id:
                raise ValueError("Должник не найден")
            
            due_date = self._parse_date(row.get("due_date"))
            if not due_date:
                raise ValueError("Неверный формат даты выплаты")
            
            debtor.name = str(row.get("name", ""))
            debtor.amount = float(row.get("amount", 0))
            debtor.due_date = due_date
            debtor.description = str(row.get("description", ""))
            
            self.results["updated"] += 1
            
        except Exception as e:
            raise ValueError(f"Ошибка обновления должника: {str(e)}")
    
    async def _process_incomes_sheet(self, df: pd.DataFrame) -> None:
        """Обработать лист с доходами"""
        if df.empty:
            return
        
        if "id" not in df.columns:
            df["id"] = None
        
        for index, row in df.iterrows():
            try:
                income_id = row.get("id")
                
                if pd.isna(income_id) or income_id is None:
                    await self._create_income(row)
                else:
                    await self._update_income(int(income_id), row)
                    # Добавляем ID в множество для сравнения
                    self.excel_ids["incomes"].add(int(income_id))
                    
            except Exception as e:
                self.results["errors"].append(f"Доход строка {index + 2}: {str(e)}")
    
    async def _create_income(self, row: pd.Series) -> None:
        """Создать новый доход"""
        try:
            next_date = self._parse_date(row.get("next_date"))
            if not next_date:
                raise ValueError("Неверный формат следующей даты")
            
            income = Income(
                user_id=self.user_id,
                name=str(row.get("name", "")),
                amount=float(row.get("amount", 0)),
                frequency=str(row.get("frequency", "monthly")),
                next_date=next_date,
                description=str(row.get("description", ""))
            )
            
            self.session.add(income)
            self.results["created"] += 1
            
        except Exception as e:
            raise ValueError(f"Ошибка создания дохода: {str(e)}")
    
    async def _update_income(self, income_id: int, row: pd.Series) -> None:
        """Обновить существующий доход"""
        try:
            income = await self.session.get(Income, income_id)
            if not income or income.user_id != self.user_id:
                raise ValueError("Доход не найден")
            
            next_date = self._parse_date(row.get("next_date"))
            if not next_date:
                raise ValueError("Неверный формат следующей даты")
            
            income.name = str(row.get("name", ""))
            income.amount = float(row.get("amount", 0))
            income.frequency = str(row.get("frequency", "monthly"))
            income.next_date = next_date
            income.description = str(row.get("description", ""))
            
            self.results["updated"] += 1
            
        except Exception as e:
            raise ValueError(f"Ошибка обновления дохода: {str(e)}")
    
    def _parse_date(self, date_value) -> Optional[date]:
        """Парсить дату из различных форматов"""
        if pd.isna(date_value) or date_value is None:
            return None
        
        try:
            if isinstance(date_value, str):
                # Пробуем разные форматы даты
                for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"]:
                    try:
                        return datetime.strptime(date_value, fmt).date()
                    except:
                        continue
                return None
            elif isinstance(date_value, datetime):
                return date_value.date()
            elif isinstance(date_value, date):
                return date_value
            else:
                return None
        except:
            return None
    
    async def _get_existing_ids(self) -> None:
        """Получить существующие ID из базы данных"""
        try:
            # Получаем ID финансовых транзакций
            finance_result = await self.session.execute(
                select(FinanceTransaction.id).where(FinanceTransaction.user_id == self.user_id)
            )
            self.existing_ids["finance"] = {row[0] for row in finance_result.fetchall()}
            
            # Получаем ID кредиторов
            creditors_result = await self.session.execute(
                select(Creditor.id).where(Creditor.user_id == self.user_id)
            )
            self.existing_ids["creditors"] = {row[0] for row in creditors_result.fetchall()}
            
            # Получаем ID должников
            debtors_result = await self.session.execute(
                select(Debtor.id).where(Debtor.user_id == self.user_id)
            )
            self.existing_ids["debtors"] = {row[0] for row in debtors_result.fetchall()}
            
            # Получаем ID доходов
            incomes_result = await self.session.execute(
                select(Income.id).where(Income.user_id == self.user_id)
            )
            self.existing_ids["incomes"] = {row[0] for row in incomes_result.fetchall()}
            
        except Exception as e:
            self.results["errors"].append(f"Ошибка получения существующих ID: {str(e)}")
    
    async def _cleanup_deleted_records(self) -> None:
        """Удалить записи, которых нет в Excel"""
        try:
            # Удаляем финансовые транзакции
            deleted_finance = self.existing_ids["finance"] - self.excel_ids["finance"]
            for record_id in deleted_finance:
                try:
                    record = await self.session.get(FinanceTransaction, record_id)
                    if record:
                        await self.session.delete(record)
                        self.results["deleted"] += 1
                except Exception as e:
                    self.results["errors"].append(f"Ошибка удаления транзакции {record_id}: {str(e)}")
            
            # Удаляем кредиторов
            deleted_creditors = self.existing_ids["creditors"] - self.excel_ids["creditors"]
            for record_id in deleted_creditors:
                try:
                    record = await self.session.get(Creditor, record_id)
                    if record:
                        await self.session.delete(record)
                        self.results["deleted"] += 1
                except Exception as e:
                    self.results["errors"].append(f"Ошибка удаления кредитора {record_id}: {str(e)}")
            
            # Удаляем должников
            deleted_debtors = self.existing_ids["debtors"] - self.excel_ids["debtors"]
            for record_id in deleted_debtors:
                try:
                    record = await self.session.get(Debtor, record_id)
                    if record:
                        await self.session.delete(record)
                        self.results["deleted"] += 1
                except Exception as e:
                    self.results["errors"].append(f"Ошибка удаления должника {record_id}: {str(e)}")
            
            # Удаляем доходы
            deleted_incomes = self.existing_ids["incomes"] - self.excel_ids["incomes"]
            for record_id in deleted_incomes:
                try:
                    record = await self.session.get(Income, record_id)
                    if record:
                        await self.session.delete(record)
                        self.results["deleted"] += 1
                except Exception as e:
                    self.results["errors"].append(f"Ошибка удаления дохода {record_id}: {str(e)}")
                    
        except Exception as e:
            self.results["errors"].append(f"Ошибка очистки удаленных записей: {str(e)}")


async def import_excel_data(session: AsyncSession, user_id: int, excel_path: Path) -> Dict[str, Any]:
    """Основная функция для импорта Excel файла"""
    importer = ExcelImporter(session, user_id)
    return await importer.import_excel_file(excel_path)
