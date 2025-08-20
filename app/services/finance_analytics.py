from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import csv
from io import StringIO

from app.db.models import FinanceTransaction, User, Creditor, Debtor, Income

# Основные группы категорий для группировки доходов и расходов
MAIN_CATEGORY_GROUPS = {
    # Расходы
    "Продукты питания": "Потребление",
    "Транспорт": "Потребление", 
    "Развлечения": "Потребление",
    "Здоровье": "Потребление",
    "Одежда": "Потребление",
    "Связь и интернет": "Потребление",
    "Коммунальные услуги": "Потребление",
    "Банковские операции": "Финансы",
    "Переводы по телефону": "Переводы",
    "Переводы": "Переводы",
    "Расходы": "Потребление",
    
    # Доходы
    "Доходы": "Доходы",
    "Поступления": "Доходы",
    "Зарплата": "Доходы",
    "Проценты": "Доходы",
    "Дивиденды": "Доходы",
    
    # Прочее
    "Прочее": "Прочее"
}

# Цвета для групп (для визуализации)
GROUP_COLORS = {
    "Потребление": "🔴",
    "Финансы": "🔵", 
    "Переводы": "🟡",
    "Доходы": "🟢",
    "Прочее": "⚪"
}


def get_main_category_group(category: str) -> str:
    """Возвращает основную группу для категории"""
    return MAIN_CATEGORY_GROUPS.get(category, "Прочее")


def get_group_color(group: str) -> str:
    """Возвращает цвет (эмодзи) для группы"""
    return GROUP_COLORS.get(group, "⚪")

# ВАЖНО: CSV загрузка добавляет ТОЛЬКО РАСХОДЫ (отрицательные суммы)
# Доходы пользователь добавляет вручную через меню "Доходы"
# Переводы и пополнения НЕ учитываются как расходы


async def get_finance_summary(session: AsyncSession, user_id: int) -> Dict[str, float]:
    """Получить сводку по финансам пользователя"""
    # Текущий месяц
    now = datetime.now()
    month_start = date(now.year, now.month, 1)
    month_end = date(now.year, now.month + 1, 1) if now.month < 12 else date(now.year + 1, 1, 1)
    
    # Доходы текущего месяца
    monthly_income_result = await session.execute(
        select(func.sum(FinanceTransaction.amount))
        .where(
            and_(
                FinanceTransaction.user_id == user_id,
                FinanceTransaction.amount > 0,
                FinanceTransaction.date >= month_start,
                FinanceTransaction.date < month_end
            )
        )
    )
    monthly_income = monthly_income_result.scalar() or 0.0
    
    # Расходы текущего месяца
    monthly_expenses_result = await session.execute(
        select(func.sum(FinanceTransaction.amount))
        .where(
            and_(
                FinanceTransaction.user_id == user_id,
                FinanceTransaction.amount < 0,
                FinanceTransaction.date >= month_start,
                FinanceTransaction.date < month_end
            )
        )
    )
    monthly_expenses = abs(monthly_expenses_result.scalar() or 0.0)
    
    # Приводим к float для корректных вычислений
    monthly_income = float(monthly_income)
    monthly_expenses = float(monthly_expenses)
    
    # Баланс текущего месяца
    monthly_balance = monthly_income - monthly_expenses
    
    # Общие кредиторы
    creditors_result = await session.execute(
        select(func.sum(Creditor.amount))
        .where(
            and_(
                Creditor.user_id == user_id,
                Creditor.is_active.is_(True)
            )
        )
    )
    total_creditors = float(creditors_result.scalar() or 0.0)
    
    # Общие должники
    debtors_result = await session.execute(
        select(func.sum(Debtor.amount))
        .where(
            and_(
                Debtor.user_id == user_id,
                Debtor.is_active.is_(True)
            )
        )
    )
    total_debtors = float(debtors_result.scalar() or 0.0)
    
    return {
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
        "monthly_balance": monthly_balance,
        "total_creditors": total_creditors,
        "total_debtors": total_debtors
    }


async def get_finance_summary_by_groups(session: AsyncSession, user_id: int, period_days: int = 30) -> Dict[str, Any]:
    """Получить сводку по финансам пользователя, сгруппированную по основным категориям"""
    # Определяем период
    now = datetime.now()
    period_start = now - timedelta(days=period_days)
    
    # Получаем все транзакции за период
    transactions_result = await session.execute(
        select(FinanceTransaction)
        .where(
            and_(
                FinanceTransaction.user_id == user_id,
                FinanceTransaction.date >= period_start.date()
            )
        )
        .order_by(FinanceTransaction.date.desc())
    )
    transactions = transactions_result.scalars().all()
    
    # Группируем по основным категориям
    groups_summary = {}
    total_income = 0.0
    total_expenses = 0.0
    
    for transaction in transactions:
        # Определяем основную группу
        main_group = get_main_category_group(transaction.category)
        
        if main_group not in groups_summary:
            groups_summary[main_group] = {
                "total": 0.0,
                "income": 0.0,
                "expenses": 0.0,
                "categories": {},
                "count": 0
            }
        
        # Добавляем к общей сумме группы (приводим к float)
        amount_float = float(transaction.amount)
        groups_summary[main_group]["total"] += amount_float
        groups_summary[main_group]["count"] += 1
        
        if amount_float > 0:
            groups_summary[main_group]["income"] += amount_float
            total_income += amount_float
        else:
            groups_summary[main_group]["expenses"] += abs(amount_float)
            total_expenses += abs(amount_float)
        
        # Группируем по подкатегориям
        if transaction.category not in groups_summary[main_group]["categories"]:
            groups_summary[main_group]["categories"][transaction.category] = {
                "total": 0.0,
                "income": 0.0,
                "expenses": 0.0,
                "count": 0
            }
        
        groups_summary[main_group]["categories"][transaction.category]["total"] += amount_float
        groups_summary[main_group]["categories"][transaction.category]["count"] += 1
        
        if amount_float > 0:
            groups_summary[main_group]["categories"][transaction.category]["income"] += amount_float
        else:
            groups_summary[main_group]["categories"][transaction.category]["expenses"] += abs(amount_float)
    
    # Сортируем группы по общей сумме (по убыванию)
    sorted_groups = sorted(
        groups_summary.items(), 
        key=lambda x: abs(x[1]["total"]), 
        reverse=True
    )
    
    return {
        "period_days": period_days,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": total_income - total_expenses,
        "groups": dict(sorted_groups)
    }


async def get_category_statistics(session: AsyncSession, user_id: int, period_days: int = 30) -> Dict[str, Any]:
    """Получить детальную статистику по категориям"""
    # Определяем период
    now = datetime.now()
    period_start = now - timedelta(days=period_days)
    
    # Получаем все транзакции за период
    transactions_result = await session.execute(
        select(FinanceTransaction)
        .where(
            and_(
                FinanceTransaction.user_id == user_id,
                FinanceTransaction.date >= period_start.date()
            )
        )
        .order_by(FinanceTransaction.date.desc())
    )
    transactions = transactions_result.scalars().all()
    
    # Группируем по категориям
    categories_stats = {}
    total_income = 0.0
    total_expenses = 0.0
    
    for transaction in transactions:
        category = transaction.category
        if category not in categories_stats:
            categories_stats[category] = {
                "total": 0.0,
                "income": 0.0,
                "expenses": 0.0,
                "count": 0,
                "main_group": get_main_category_group(category)
            }
        
        # Приводим к float для корректных вычислений
        amount_float = float(transaction.amount)
        categories_stats[category]["total"] += amount_float
        categories_stats[category]["count"] += 1
        
        if amount_float > 0:
            categories_stats[category]["income"] += amount_float
            total_income += amount_float
        else:
            categories_stats[category]["expenses"] += abs(amount_float)
            total_expenses += abs(amount_float)
    
    # Сортируем категории по общей сумме (по убыванию)
    sorted_categories = sorted(
        categories_stats.items(), 
        key=lambda x: abs(x[1]["total"]), 
        reverse=True
    )
    
    return {
        "period_days": period_days,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": total_income - total_expenses,
        "categories": dict(sorted_categories)
    }


async def get_creditors(session: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Получить список кредиторов пользователя"""
    result = await session.execute(
        select(Creditor)
        .where(
            and_(
                Creditor.user_id == user_id,
                Creditor.is_active.is_(True)
            )
        )
        .order_by(Creditor.due_date)
    )
    creditors = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "name": c.name,
            "amount": float(c.amount),
            "due_date": c.due_date.strftime("%d.%m.%Y"),
            "description": c.description
        }
        for c in creditors
    ]


async def get_debtors(session: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Получить список должников пользователя"""
    result = await session.execute(
        select(Debtor)
        .where(
            and_(
                Debtor.user_id == user_id,
                Debtor.is_active.is_(True)
            )
        )
        .order_by(Debtor.due_date)
    )
    debtors = result.scalars().all()
    
    return [
        {
            "id": d.id,
            "name": d.name,
            "amount": float(d.amount),
            "due_date": d.due_date.strftime("%d.%m.%Y"),
            "description": d.description
        }
        for d in debtors
    ]


async def process_bank_csv(session: AsyncSession, user_id: int, csv_content: str, bank_type: str) -> Dict[str, Any]:
    """Обработать CSV файл банковской выписки"""
    try:
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        print(f"DEBUG: Тип банка: {bank_type}")
        print(f"DEBUG: Количество строк: {len(rows)}")
        if rows:
            print(f"DEBUG: Первая строка: {rows[0]}")
        
        if not rows:
            return {
                "processed": 0,
                "added": 0,
                "skipped": 0,
                "errors": ["CSV файл пуст или не содержит данных"]
            }
        
        processed = 0
        added = 0
        skipped = 0
        errors = []
        
        for row_num, row in enumerate(rows, 1):
            try:
                processed += 1
                
                # Парсим строку в зависимости от типа банка
                transaction_data = parse_bank_row(row, bank_type)
                
                if not transaction_data:
                    print(f"DEBUG: Строка {row_num} пропущена, данные: {row}")
                    skipped += 1
                    continue
                
                # Для MBank учитываем все транзакции (расходы, доходы, переводы)
                # Для других банков - только расходы
                if bank_type == "MBank" or transaction_data["amount"] < 0:
                    # Создаем транзакцию
                    transaction = FinanceTransaction(
                        user_id=user_id,
                        date=transaction_data["date"],
                        amount=transaction_data["amount"],
                        category=transaction_data["category"],
                        description=transaction_data["description"]
                    )
                    
                    session.add(transaction)
                    added += 1
                else:
                    print(f"DEBUG: Строка {row_num} пропущена (не расход для банка {bank_type}): {row}")
                    skipped += 1
                
            except Exception as e:
                error_msg = f"Строка {row_num}: {str(e)}"
                print(f"DEBUG: {error_msg}")
                errors.append(error_msg)
                skipped += 1
        
        # Сохраняем изменения
        await session.commit()
        
        return {
            "processed": processed,
            "added": added,
            "skipped": skipped,
            "errors": errors
        }
        
    except Exception as e:
        print(f"DEBUG: Ошибка обработки файла: {e}")
        return {
            "processed": 0,
            "added": 0,
            "skipped": 0,
            "errors": [f"Ошибка обработки файла: {str(e)}"]
        }


def parse_bank_row(row: Dict[str, str], bank_type: str) -> Optional[Dict[str, Any]]:
    """Парсит строку CSV в зависимости от типа банка"""
    try:
        if bank_type == "Альфа-Банк":
            return parse_alpha_row(row)
        elif bank_type == "Т-Банк":
            return parse_tbank_row(row)
        elif bank_type == "MBank":
            return parse_mbank_row(row)
        else:
            return parse_generic_row(row)
    except:
        return None





def parse_alpha_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Парсит строку Альфа-Банка"""
    try:
        print(f"DEBUG: Парсинг строки Альфа-Банка: {row}")
        
        # Альфа-Банк: используем основные поля для транзакции
        date_str = row.get("operationDate") or row.get("transactionDate") or row.get("operationdate") or row.get("transactiondate")
        amount_str = row.get("amount")
        description = row.get("comment") or row.get("merchant") or ""
        category = row.get("category") or ""
        merchant = row.get("merchant") or ""
        transaction_type = row.get("type") or ""
        
        print(f"DEBUG: Альфа-Банк - найдены значения - дата: {date_str}, сумма: {amount_str}, описание: {description}, категория: {category}, merchant: {merchant}, type: {transaction_type}")
        
        if not date_str or not amount_str:
            print(f"DEBUG: Альфа-Банк - отсутствует дата или сумма")
            return None
            
        # Парсим дату (Альфа-Банк использует разные форматы)
        date = None
        for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d", "%d/%m/%Y"]:
            try:
                date = datetime.strptime(date_str, fmt).date()
                print(f"DEBUG: Альфа-Банк - дата успешно распарсена: {date}")
                break
            except:
                continue
                
        if not date:
            print(f"DEBUG: Альфа-Банк - не удалось распарсить дату: {date_str}")
            return None
            
        # Парсим сумму (убираем пробелы, заменяем запятую на точку, убираем валюту)
        amount_str = amount_str.replace(" ", "").replace(",", ".").replace("₽", "").replace("руб", "").replace("рублей", "")
        try:
            amount = float(amount_str)
            print(f"DEBUG: Альфа-Банк - сумма успешно распарсена: {amount}")
        except ValueError:
            print(f"DEBUG: Альфа-Банк - не удалось распарсить сумму: {amount_str}")
            return None
        
        # Проверяем тип транзакции - добавляем только списания (расходы)
        if transaction_type.lower() not in ["списание", "debit", "debit transaction"]:
            # Для всех остальных типов (пополнения, переводы и т.д.) - пропускаем
            print(f"DEBUG: Альфа-Банк - пропускаем транзакцию типа '{transaction_type}' (не списание)")
            return None
        
        # Проверяем, не является ли это переводом или доходом
        if is_transfer_or_income(description, category):
            print(f"DEBUG: Альфа-Банк - пропускаем перевод/доход: {description}, категория: {category}")
            return None
        
        # Для списаний делаем сумму отрицательной (расход)
        amount = -abs(amount)
        print(f"DEBUG: Альфа-Банк - списание, сумма сделана отрицательной: {amount}")
        
        # Если есть категория от банка, используем её, иначе определяем по описанию
        if category and category.strip():
            final_category = category.strip()
            print(f"DEBUG: Альфа-Банк - используется категория от банка: {final_category}")
        else:
            final_category = determine_category(description)
            print(f"DEBUG: Альфа-Банк - определена категория по описанию: {final_category}")
        
        # Создаем полное описание
        full_description_parts = []
        if merchant:
            full_description_parts.append(f"Merchant: {merchant}")
        if description:
            full_description_parts.append(description)
        if row.get("mcc"):
            full_description_parts.append(f"MCC: {row['mcc']}")
        if row.get("bonusValue"):
            full_description_parts.append(f"Бонус: {row['bonusValue']}")
        if row.get("bonusTitle"):
            full_description_parts.append(f"Тип бонуса: {row['bonusTitle']}")
        
        if full_description_parts:
            full_description = " | ".join(full_description_parts)
        else:
            full_description = description or "Операция"
        
        print(f"DEBUG: Альфа-Банк - итоговое описание: {full_description}")
        
        return {
            "date": date,
            "amount": amount,
            "category": final_category,
            "description": full_description
        }
    except Exception as e:
        print(f"DEBUG: Альфа-Банк - ошибка парсинга строки: {e}")
        return None



def parse_tbank_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Парсит строку Т-Банка"""
    try:
        print(f"DEBUG: Парсинг строки Т-Банка: {row}")
        
        # Т-Банк: используем основные поля для транзакции
        date_str = row.get("Дата операции") or row.get("Дата платежа")
        amount_str = row.get("Сумма операции") or row.get("Сумма платежа")
        description = row.get("Описание") or ""
        category = row.get("Категория") or ""
        
        print(f"DEBUG: Т-Банк - найдены значения - дата: {date_str}, сумма: {amount_str}, описание: {description}, категория: {category}")
        
        if not date_str or not amount_str:
            print(f"DEBUG: Т-Банк - отсутствует дата или сумма")
            return None
            
        # Парсим дату (Т-Банк обычно использует формат ДД.ММ.ГГГГ)
        date = None
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"]:
            try:
                date = datetime.strptime(date_str, fmt).date()
                print(f"DEBUG: Т-Банк - дата успешно распарсена: {date}")
                break
            except:
                continue
                
        if not date:
            print(f"DEBUG: Т-Банк - не удалось распарсить дату: {date_str}")
            return None
            
        # Парсим сумму (убираем пробелы, заменяем запятую на точку, убираем валюту)
        amount_str = amount_str.replace(" ", "").replace(",", ".").replace("₽", "").replace("руб", "").replace("рублей", "")
        try:
            amount = float(amount_str)
            print(f"DEBUG: Т-Банк - сумма успешно распарсена: {amount}")
        except ValueError:
            print(f"DEBUG: Т-Банк - не удалось распарсить сумму: {amount_str}")
            return None
        
        # Проверяем, не является ли это переводом или доходом
        if is_transfer_or_income(description, category):
            print(f"DEBUG: Т-Банк - пропускаем перевод/доход: {description}, категория: {category}")
            return None
        
        # Т-Банк: добавляем только расходы (отрицательные суммы)
        # Если сумма положительная, делаем её отрицательной (это расход)
        if amount > 0:
            amount = -amount
            print(f"DEBUG: Т-Банк - положительная сумма сделана отрицательной (расход): {amount}")
        
        # Если есть категория от банка, используем её, иначе определяем по описанию
        if category and category.strip():
            final_category = category.strip()
            print(f"DEBUG: Т-Банк - используется категория от банка: {final_category}")
        else:
            final_category = determine_category(description)
            print(f"DEBUG: Т-Банк - определена категория по описанию: {final_category}")
        
        # Добавляем дополнительную информацию в описание
        additional_info = []
        if row.get("MCC"):
            additional_info.append(f"MCC: {row['MCC']}")
        if row.get("Кэшбэк"):
            additional_info.append(f"Кэшбэк: {row['Кэшбэк']}")
        if row.get("Бонусы (включая кэшбэк)"):
            additional_info.append(f"Бонусы: {row['Бонусы (включая кэшбэк)']}")
        
        if additional_info:
            full_description = f"{description} | {' | '.join(additional_info)}"
        else:
            full_description = description
        
        print(f"DEBUG: Т-Банк - итоговое описание: {full_description}")
        
        return {
            "date": date,
            "amount": amount,
            "category": final_category,
            "description": full_description
        }
    except Exception as e:
        print(f"DEBUG: Т-Банк - ошибка парсинга строки: {e}")
        return None


def parse_mbank_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Парсит строку MBank"""
    try:
        print(f"DEBUG: Парсинг строки MBank: {row}")
        
        # MBank: используем основные поля для транзакции
        date_str = row.get("Дата") or row.get("дата")
        recipient = row.get("Получатель/Плательщик") or row.get("получатель/плательщик") or ""
        expense_str = row.get("Расход") or row.get("расход") or "0,00"
        income_str = row.get("Приход") or row.get("приход") or "0,00"
        operation = row.get("Операция") or row.get("операция") or ""
        
        print(f"DEBUG: MBank - найдены значения - дата: {date_str}, получатель: {recipient}, расход: {expense_str}, приход: {income_str}, операция: {operation}")
        
        if not date_str or not date_str.strip():
            print(f"DEBUG: MBank - отсутствует дата")
            return None
            
        # Пропускаем служебные строки (итоги, заголовки и т.д.)
        date_str_lower = date_str.lower().strip()
        if any(skip_word in date_str_lower for skip_word in [
            "средства на начало периода", "средства на конец периода",
            "зачисления за период", "списания за период", "дата:"
        ]):
            print(f"DEBUG: MBank - пропускаем служебную строку: {date_str}")
            return None
            
        # Парсим дату (MBank использует формат ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ)
        date = None
        for fmt in ["%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"]:
            try:
                parsed_datetime = datetime.strptime(date_str, fmt)
                date = parsed_datetime.date()
                print(f"DEBUG: MBank - дата успешно распарсена: {date} (из {date_str})")
                break
            except:
                continue
                
        if not date:
            print(f"DEBUG: MBank - не удалось распарсить дату: {date_str}")
            return None
            
        # Парсим суммы (убираем пробелы, заменяем запятую на точку, убираем валюту)
        expense_str = expense_str.replace(" ", "").replace(",", ".").replace("KGS", "").replace("₸", "").strip()
        income_str = income_str.replace(" ", "").replace(",", ".").replace("KGS", "").replace("₸", "").strip()
        
        try:
            expense = float(expense_str) if expense_str != "0,00" and expense_str != "0.00" else 0.0
            income = float(income_str) if income_str != "0,00" and income_str != "0.00" else 0.0
            print(f"DEBUG: MBank - суммы успешно распарсены - расход: {expense}, приход: {income}")
        except ValueError:
            print(f"DEBUG: MBank - не удалось распарсить суммы: расход={expense_str}, приход={income_str}")
            return None
        
        # Определяем тип транзакции и сумму
        if expense > 0 and income == 0:
            # Это расход
            amount = -expense
            transaction_type = "расход"
        elif income > 0 and expense == 0:
            # Это приход
            amount = income
            transaction_type = "приход"
        else:
            # Если обе суммы 0 или обе больше 0 - пропускаем
            print(f"DEBUG: MBank - пропускаем транзакцию с неопределенным типом: расход={expense}, приход={income}")
            return None
            
        # Пропускаем строки без получателя и операции (пустые транзакции)
        if not recipient.strip() and not operation.strip():
            print(f"DEBUG: MBank - пропускаем пустую транзакцию: получатель='{recipient}', операция='{operation}'")
            return None
        
        # Для MBank учитываем и расходы, и приходы, а также переводы по номеру телефона
        # Определяем категорию по описанию операции
        category = determine_mbank_category(operation, recipient, transaction_type)
        print(f"DEBUG: MBank - определена категория: {category}")
        
        # Создаем описание
        description_parts = []
        if recipient:
            description_parts.append(f"Получатель: {recipient}")
        if operation:
            description_parts.append(operation)
        
        full_description = " | ".join(description_parts) if description_parts else "Операция MBank"
        print(f"DEBUG: MBank - итоговое описание: {full_description}")
        
        return {
            "date": date,
            "amount": amount,
            "category": category,
            "description": full_description
        }
    except Exception as e:
        print(f"DEBUG: MBank - ошибка парсинга строки: {e}")
        return None



def parse_generic_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Парсит строку с универсальными заголовками"""
    try:
        print(f"DEBUG: Парсинг универсальной строки: {row}")
        
        # Пробуем найти стандартные колонки
        date_str = row.get("date") or row.get("Дата") or row.get("Date") or row.get("дата")
        amount_str = row.get("amount") or row.get("Сумма") or row.get("Amount") or row.get("сумма")
        description = row.get("description") or row.get("Описание") or row.get("Description") or row.get("описание") or row.get("Назначение") or row.get("назначение") or ""
        
        print(f"DEBUG: Найдены значения - дата: {date_str}, сумма: {amount_str}, описание: {description}")
        
        if not date_str or not amount_str:
            print(f"DEBUG: Отсутствует дата или сумма")
            return None
            
        # Пробуем разные форматы даты
        date = None
        for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"]:
            try:
                date = datetime.strptime(date_str, fmt).date()
                print(f"DEBUG: Дата успешно распарсена: {date}")
                break
            except:
                continue
                
        if not date:
            print(f"DEBUG: Не удалось распарсить дату: {date_str}")
            return None
            
        # Парсим сумму (убираем пробелы, заменяем запятую на точку, убираем валюту)
        amount_str = amount_str.replace(" ", "").replace(",", ".").replace("₽", "").replace("руб", "").replace("рублей", "")
        try:
            amount = float(amount_str)
            print(f"DEBUG: Сумма успешно распарсена: {amount}")
        except ValueError:
            print(f"DEBUG: Не удалось распарсить сумму: {amount_str}")
            return None
        
        # Проверяем, не является ли это переводом или доходом
        if is_transfer_or_income(description):
            print(f"DEBUG: Универсальный - пропускаем перевод/доход: {description}")
            return None
        
        # Универсальный парсинг: добавляем только расходы (отрицательные суммы)
        # Если сумма положительная, делаем её отрицательной (это расход)
        if amount > 0:
            amount = -amount
            print(f"DEBUG: Положительная сумма сделана отрицательной (расход): {amount}")
        
        category = determine_category(description)
        print(f"DEBUG: Определена категория: {category}")
        
        return {
            "date": date,
            "amount": amount,
            "category": category,
            "description": description
        }
    except Exception as e:
        print(f"DEBUG: Ошибка парсинга универсальной строки: {e}")
        return None


def is_transfer_or_income(description: str, category: str = "") -> bool:
    """Проверяет, является ли транзакция переводом или доходом (которые не нужно учитывать)"""
    description_lower = description.lower()
    category_lower = category.lower()
    
    # Ключевые слова для переводов
    transfer_keywords = [
        "перевод", "transfer", "переводы", "пополнение", "зачисление",
        "внесение", "поступление", "от", "кэшбэк", "кешбэк", "cashback",
        "бонус", "bonus", "возврат", "refund", "компенсация"
    ]
    
    # Ключевые слова для доходов
    income_keywords = [
        "зарплата", "salary", "доход", "income", "выплата", "начисление",
        "dividend", "дивиденд", "процент", "interest", "премия"
    ]
    
    # Категории, которые нужно пропускать
    skip_categories = [
        "переводы", "transfers", "пополнения", "пополнение", "доходы", 
        "income", "бонусы", "bonus", "кэшбэк", "cashback", "проценты"
    ]
    
    # Проверяем описание
    for keyword in transfer_keywords + income_keywords:
        if keyword in description_lower:
            return True
    
    # Проверяем категорию
    for skip_cat in skip_categories:
        if skip_cat in category_lower:
            return True
    
    return False


def determine_category(description: str) -> str:
    """Определяет категорию по описанию транзакции"""
    description_lower = description.lower()
    
    # Продукты питания
    if any(word in description_lower for word in ["продукты", "еда", "магазин", "супермаркет", "кафе", "ресторан", "кофе"]):
        return "Продукты питания"
    
    # Транспорт
    elif any(word in description_lower for word in ["метро", "автобус", "такси", "uber", "яндекс", "бензин", "топливо"]):
        return "Транспорт"
    
    # Развлечения
    elif any(word in description_lower for word in ["кино", "театр", "концерт", "музей", "игра", "развлечения"]):
        return "Развлечения"
    
    # Здоровье
    elif any(word in description_lower for word in ["аптека", "врач", "больница", "клиника", "лекарства"]):
        return "Здоровье"
    
    # Одежда
    elif any(word in description_lower for word in ["одежда", "обувь", "магазин одежды", "zara", "h&m"]):
        return "Одежда"
    
    # Связь и интернет
    elif any(word in description_lower for word in ["телефон", "интернет", "связь", "мтс", "билайн", "мегафон"]):
        return "Связь и интернет"
    
    # Коммунальные услуги
    elif any(word in description_lower for word in ["жкх", "квартплата", "электричество", "газ", "вода"]):
        return "Коммунальные услуги"
    
    # Доходы
    elif any(word in description_lower for word in ["зарплата", "доход", "поступление", "перевод"]):
        return "Доходы"
    
    else:
        return "Прочее"


def determine_mbank_category(operation: str, recipient: str, transaction_type: str) -> str:
    """Определяет категорию для транзакций MBank по описанию операции"""
    operation_lower = operation.lower()
    recipient_lower = recipient.lower()
    
    # Переводы по номеру телефона (учитываем как отдельную категорию)
    if any(word in operation_lower for word in ["перевод по номеру телефона", "перевод по номеру телефона qr", "перевод по mbank"]):
        return "Переводы по телефону"
    
    # Продукты питания
    if any(word in operation_lower for word in ["globus", "гипермаркет", "супермаркет", "магазин", "продукты", "еда", "кафе", "ресторан", "кофе"]):
        return "Продукты питания"
    
    # Транспорт
    elif any(word in operation_lower for word in ["яндекс", "yandex", "самокат", "scooter", "такси", "uber", "бензин", "топливо", "atm", "банкомат"]):
        return "Транспорт"
    
    # Развлечения
    elif any(word in operation_lower for word in ["кино", "театр", "концерт", "музей", "игра", "развлечения"]):
        return "Развлечения"
    
    # Здоровье
    elif any(word in operation_lower for word in ["аптека", "врач", "больница", "клиника", "лекарства"]):
        return "Здоровье"
    
    # Одежда
    elif any(word in operation_lower for word in ["одежда", "обувь", "магазин одежды", "zara", "h&m"]):
        return "Одежда"
    
    # Связь и интернет
    elif any(word in operation_lower for word in ["телефон", "интернет", "связь", "мтс", "билайн", "мегафон", "o!", "o!", "obank", "o!bank"]):
        return "Связь и интернет"
    
    # Коммунальные услуги
    elif any(word in operation_lower for word in ["жкх", "квартплата", "электричество", "газ", "вода", "госуслуги"]):
        return "Коммунальные услуги"
    
    # Банковские операции
    elif any(word in operation_lower for word in ["cash in", "cash out", "пэй 24", "pay24", "megapay", "umai", "гринтелеком", "комиссия"]):
        return "Банковские операции"
    
    # Доходы (для приходов)
    elif transaction_type == "приход":
        if any(word in operation_lower for word in ["зарплата", "доход", "поступление", "перевод", "cash in"]):
            return "Доходы"
        else:
            return "Поступления"
    
    # Переводы (для расходов)
    elif transaction_type == "расход":
        if any(word in operation_lower for word in ["перевод", "transfer"]):
            return "Переводы"
        else:
            return "Расходы"
    
    else:
        return "Прочее"






