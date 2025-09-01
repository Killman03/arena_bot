from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import session_scope
from app.db.models import User, Creditor, Debtor, Income, FinanceTransaction, FinancialGoal
from app.keyboards.common import creditor_debtor_menu, back_main_menu
from app.services.finance_reminders import send_finance_reminders_for_user
from app.services.finance_todo_manager import create_todo_for_financial_obligations
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.services.llm import deepseek_complete

router = Router()


class CreditorStates(StatesGroup):
    """Состояния для добавления/редактирования кредитора"""
    waiting_for_name = State()
    waiting_for_amount = State()
    waiting_for_due_date = State()
    waiting_for_description = State()


class DebtorStates(StatesGroup):
    """Состояния для добавления/редактирования должника"""
    waiting_for_name = State()
    waiting_for_amount = State()
    waiting_for_due_date = State()
    waiting_for_description = State()


class IncomeStates(StatesGroup):
    """Состояния для добавления дохода"""
    waiting_for_name = State()
    waiting_for_amount = State()
    waiting_for_frequency = State()
    waiting_for_next_date = State()
    waiting_for_description = State()
    waiting_for_regular_amount = State()
    waiting_for_extra_amount = State()
    waiting_for_income_description = State()


class ExpenseStates(StatesGroup):
    """Состояния для добавления расхода"""
    waiting_for_amount = State()
    waiting_for_description = State()


class FinancialGoalStates(StatesGroup):
    """Состояния для добавления финансовой цели"""
    waiting_for_name = State()
    waiting_for_target_amount = State()
    waiting_for_monthly_percentage = State()
    waiting_for_deadline = State()
    waiting_for_description = State()
    waiting_for_contribution_amount = State()


@router.callback_query(F.data == "creditor_add")
async def creditor_add_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать добавление кредитора"""
    await state.set_state(CreditorStates.waiting_for_name)
    await cb.message.edit_text(
        "💸 <b>Добавление кредитора</b>\n\n"
        "<b>Кредитор</b> - это человек/организация, которой ВЫ должны деньги.\n\n"
        "<b>Шаг 1/4:</b> Введите имя кредитора (кому ВЫ должны деньги):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(CreditorStates.waiting_for_name)
async def creditor_name_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать имя кредитора"""
    await state.update_data(name=message.text)
    await state.set_state(CreditorStates.waiting_for_amount)
    await message.answer(
        "<b>Шаг 2/4:</b> Введите сумму долга (только число):",
        parse_mode="HTML"
    )


@router.message(CreditorStates.waiting_for_amount)
async def creditor_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать сумму кредитора"""
    try:
        amount = float(message.text)
        await state.update_data(amount=amount)
        await state.set_state(CreditorStates.waiting_for_due_date)
        await message.answer(
            "<b>Шаг 3/4:</b> Введите дату выплаты в формате ДД.ММ.ГГГГ:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.message(CreditorStates.waiting_for_due_date)
async def creditor_due_date_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать дату выплаты кредитора"""
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        await state.update_data(due_date=due_date)
        await state.set_state(CreditorStates.waiting_for_description)
        await message.answer(
            "<b>Шаг 4/4:</b> Введите описание (необязательно) или отправьте точку (.) для пропуска:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ")


@router.message(CreditorStates.waiting_for_description)
async def creditor_description_handler(message: types.Message, state: FSMContext) -> None:
    """Завершить добавление кредитора"""
    description = message.text if message.text != "." else None
    await state.update_data(description=description)
    
    data = await state.get_data()
    
    user = message.from_user
    if not user:
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        creditor = Creditor(
            user_id=db_user.id,
            name=data["name"],
            amount=Decimal(str(data["amount"])),
            due_date=data["due_date"],
            description=data["description"]
        )
        session.add(creditor)
        await session.commit()
    
    await state.clear()
    await message.answer(
        f"✅ <b>Кредитор добавлен!</b>\n\n"
        f"👤 <b>Имя:</b> {data['name']}\n"
        f"💰 <b>Сумма долга:</b> {data['amount']:,.2f} ₽ (ВЫ должны)\n"
        f"📅 <b>Дата выплаты:</b> {data['due_date'].strftime('%d.%m.%Y')}\n"
        f"📝 <b>Описание:</b> {data['description'] or 'Не указано'}",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "debtor_add")
async def debtor_add_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать добавление должника"""
    await state.set_state(DebtorStates.waiting_for_name)
    await cb.message.edit_text(
        "🏦 <b>Добавление должника</b>\n\n"
        "<b>Должник</b> - это человек/организация, которая должна деньги ВАМ.\n\n"
        "<b>Шаг 1/4:</b> Введите имя должника (кто должен деньги ВАМ):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(DebtorStates.waiting_for_name)
async def debtor_name_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать имя должника"""
    await state.update_data(name=message.text)
    await state.set_state(DebtorStates.waiting_for_amount)
    await message.answer(
        "<b>Шаг 2/4:</b> Введите сумму долга (только число):",
        parse_mode="HTML"
    )


@router.message(DebtorStates.waiting_for_amount)
async def debtor_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать сумму должника"""
    try:
        amount = float(message.text)
        await state.update_data(amount=amount)
        await state.set_state(DebtorStates.waiting_for_due_date)
        await message.answer(
            "<b>Шаг 3/4:</b> Введите дату выплаты в формате ДД.ММ.ГГГГ:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.message(DebtorStates.waiting_for_due_date)
async def debtor_due_date_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать дату выплаты должника"""
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        await state.update_data(due_date=due_date)
        await state.set_state(DebtorStates.waiting_for_description)
        await message.answer(
            "<b>Шаг 4/4:</b> Введите описание (необязательно) или отправьте точку (.) для пропуска:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ")


@router.message(DebtorStates.waiting_for_description)
async def debtor_description_handler(message: types.Message, state: FSMContext) -> None:
    """Завершить добавление должника"""
    description = message.text if message.text != "." else None
    await state.update_data(description=description)
    
    data = await state.get_data()
    
    user = message.from_user
    if not user:
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        debtor = Debtor(
            user_id=db_user.id,
            name=data["name"],
            amount=Decimal(str(data["amount"])),
            due_date=data["due_date"],
            description=data["description"]
        )
        session.add(debtor)
        await session.commit()
    
    await state.clear()
    await message.answer(
        f"✅ <b>Должник добавлен!</b>\n\n"
        f"👤 <b>Имя:</b> {data['name']}\n"
        f"💰 <b>Сумма долга:</b> {data['amount']:,.2f} ₽ (должен ВАМ)\n"
        f"📅 <b>Дата выплаты:</b> {data['due_date'].strftime('%d.%m.%Y')}\n"
        f"📝 <b>Описание:</b> {data['description'] or 'Не указано'}",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("creditor_view:"))
async def creditor_view(cb: types.CallbackQuery) -> None:
    """Показать детали кредитора"""
    creditor_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        creditor = await session.get(Creditor, creditor_id)
        if not creditor:
            await cb.answer("Кредитор не найден")
            return
        
        text = f"💸 <b>Кредитор: {creditor.name}</b>\n\n"
        text += f"💰 <b>Сумма:</b> {float(creditor.amount):,.2f} ₽\n"
        text += f"📅 <b>Дата выплаты:</b> {creditor.due_date.strftime('%d.%m.%Y')}\n"
        text += f"📝 <b>Описание:</b> {creditor.description or 'Не указано'}\n"
        text += f"📅 <b>Добавлен:</b> {creditor.created_at.strftime('%d.%m.%Y')}"
        
        await cb.message.edit_text(text, reply_markup=creditor_debtor_menu("creditor", creditor_id), parse_mode="HTML")
    
    await cb.answer()


@router.callback_query(F.data.startswith("debtor_view:"))
async def debtor_view(cb: types.CallbackQuery) -> None:
    """Показать детали должника"""
    debtor_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        debtor = await session.get(Debtor, debtor_id)
        if not debtor:
            await cb.answer("Должник не найден")
            return
        
        text = f"🏦 <b>Должник: {debtor.name}</b>\n\n"
        text += f"💰 <b>Сумма:</b> {float(debtor.amount):,.2f} ₽\n"
        text += f"📅 <b>Дата выплаты:</b> {debtor.due_date.strftime('%d.%m.%Y')}\n"
        text += f"📝 <b>Описание:</b> {debtor.description or 'Не указано'}\n"
        text += f"📅 <b>Добавлен:</b> {debtor.created_at.strftime('%d.%m.%Y')}"
        
        await cb.message.edit_text(text, reply_markup=creditor_debtor_menu("debtor", debtor_id), parse_mode="HTML")
    
    await cb.answer()


@router.callback_query(F.data.startswith("creditor_delete:") | F.data.startswith("debtor_delete:"))
async def delete_creditor_debtor(cb: types.CallbackQuery) -> None:
    """Удалить кредитора или должника"""
    parts = cb.data.split(":")
    item_type = parts[0]
    item_id = int(parts[1])
    
    async with session_scope() as session:
        if item_type == "creditor_delete":
            item = await session.get(Creditor, item_id)
            item_name = "кредитор"
        else:
            item = await session.get(Debtor, item_id)
            item_name = "должник"
        
        if not item:
            await cb.answer(f"{item_name.title()} не найден")
            return
        
        name = item.name
        session.delete(item)
        await session.commit()
    
    await cb.message.edit_text(
        f"🗑️ <b>{item_name.title()} удален!</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"✅ Запись успешно удалена из базы данных.",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("creditor_payment:") | F.data.startswith("debtor_payment:"))
async def mark_payment(cb: types.CallbackQuery) -> None:
    """Отметить выплату по кредитору или должнику"""
    parts = cb.data.split(":")
    item_type = parts[0]
    item_id = int(parts[1])
    
    async with session_scope() as session:
        if item_type == "creditor_payment":
            item = await session.get(Creditor, item_id)
            item_name = "кредитор"
        else:
            item = await session.get(Debtor, item_id)
            item_name = "должник"
        
        if not item:
            await cb.answer(f"{item_name.title()} не найден")
            return
        
        # Деактивировать запись
        item.is_active = False
        await session.commit()
    
    await cb.message.edit_text(
        f"✅ <b>Выплата отмечена!</b>\n\n"
        f"👤 <b>{item_name.title()}:</b> {item.name}\n"
        f"💰 <b>Сумма:</b> {float(item.amount):,.2f} ₽\n"
        f"✅ Запись деактивирована.",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


# ===== ОБРАБОТЧИКИ ДЛЯ РАСХОДОВ =====

@router.callback_query(F.data == "expense_add")
async def expense_add_start(cb: types.CallbackQuery) -> None:
    """Начать добавление расхода - показать меню категорий"""
    from app.keyboards.common import finance_expense_menu
    await cb.message.edit_text(
        "💸 <b>Добавление расхода</b>\n\n"
        "Выберите категорию расхода:",
        reply_markup=finance_expense_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("expense_category_"))
async def expense_category_selected(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработать выбор категории расхода"""
    category = cb.data.replace("expense_category_", "")
    
    # Маппинг категорий для красивого отображения
    category_names = {
        "purchases": "Покупки",
        "food": "Питание", 
        "transport": "Транспорт",
        "utilities": "Коммунальные услуги",
        "health": "Здоровье",
        "entertainment": "Развлечения",
        "communication": "Связь и интернет",
        "clothing": "Одежда",
        "education": "Образование",
        "banking": "Банковские услуги",
        "other": "Прочее"
    }
    
    category_name = category_names.get(category, category)
    
    await state.update_data(category=category_name)
    await state.set_state(ExpenseStates.waiting_for_amount)
    
    await cb.message.edit_text(
        f"💸 <b>Добавление расхода</b>\n\n"
        f"📂 <b>Категория:</b> {category_name}\n\n"
        f"<b>Шаг 1/2:</b> Введите сумму расхода (только число):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(ExpenseStates.waiting_for_amount)
async def expense_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать сумму расхода"""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Введите корректную сумму.")
            return
            
        await state.update_data(amount=amount)
        await state.set_state(ExpenseStates.waiting_for_description)
        
        await message.answer(
            "<b>Шаг 2/2:</b> Введите описание расхода (необязательно) или отправьте точку (.) для пропуска:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.message(ExpenseStates.waiting_for_description)
async def expense_description_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать описание расхода и сохранить"""
    data = await state.get_data()
    amount = data.get("amount")
    category = data.get("category")
    description = message.text if message.text != "." else ""
    
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Создаем транзакцию расхода (отрицательная сумма)
            from app.db.models import FinanceTransaction
            from datetime import date
            
            expense = FinanceTransaction(
                user_id=db_user.id,
                date=date.today(),
                amount=-abs(amount),  # Отрицательная сумма для расхода
                category=category,
                description=description
            )
            
            session.add(expense)
            await session.commit()
        
        # Формируем сообщение об успехе
        success_text = f"✅ <b>Расход добавлен!</b>\n\n"
        success_text += f"💰 <b>Сумма:</b> {amount:,.2f} ₽\n"
        success_text += f"📂 <b>Категория:</b> {category}\n"
        if description:
            success_text += f"📝 <b>Описание:</b> {description}\n"
        success_text += f"📅 <b>Дата:</b> {date.today().strftime('%d.%m.%Y')}"
        
        await message.answer(
            success_text,
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при добавлении расхода:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        await state.clear()


# ===== ОБРАБОТЧИК ДЛЯ ИМПОРТА EXCEL =====

@router.callback_query(F.data == "finance_import_excel")
async def finance_import_excel_start(cb: types.CallbackQuery) -> None:
    """Начать импорт Excel файла"""
    await cb.message.edit_text(
        "📤 <b>Импорт Excel файла</b>\n\n"
        "📋 <b>Как использовать:</b>\n"
        "1️⃣ Скачайте Excel файл через кнопку '📊 Экспорт Excel'\n"
        "2️⃣ Отредактируйте данные в Excel (измените суммы, даты, описания)\n"
        "3️⃣ Загрузите отредактированный файл сюда\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Не удаляйте колонку 'id' - она нужна для обновления\n"
        "• Новые записи добавляйте без id (оставьте пустым)\n"
        "• <b>Для удаления записи просто удалите строку из Excel</b>\n"
        "• <b>Удаленные строки будут автоматически удалены из базы данных</b>\n\n"
        "📎 <b>Отправьте Excel файл (.xlsx):</b>",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


# ===== ОБРАБОТЧИКИ ДЛЯ УПРАВЛЕНИЯ ДОХОДАМИ =====

@router.callback_query(F.data == "income_add_regular")
async def income_add_regular_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать добавление постоянного дохода"""
    await cb.message.edit_text(
        "💰 <b>Добавление постоянного дохода</b>\n\n"
        "Введите сумму постоянного дохода:",
        parse_mode="HTML"
    )
    await state.set_state(IncomeStates.waiting_for_regular_amount)
    await cb.answer()


@router.message(IncomeStates.waiting_for_regular_amount)
async def income_regular_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать сумму постоянного дохода"""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Введите корректную сумму.")
            return
            
        await state.update_data(amount=amount, is_regular=True)
        await state.set_state(IncomeStates.waiting_for_income_description)
        
        await message.answer(
            "<b>Шаг 2/2:</b> Введите описание дохода (необязательно) или отправьте точку (.) для пропуска:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.callback_query(F.data == "income_add_extra")
async def income_add_extra_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать добавление внепланового дохода"""
    await cb.message.edit_text(
        "💰 <b>Добавление внепланового дохода</b>\n\n"
        "Введите сумму внепланового дохода:",
        parse_mode="HTML"
    )
    await state.set_state(IncomeStates.waiting_for_extra_amount)
    await cb.answer()


@router.message(IncomeStates.waiting_for_extra_amount)
async def income_extra_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать сумму внепланового дохода"""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Введите корректную сумму.")
            return
            
        await state.update_data(amount=amount, is_regular=False)
        await state.set_state(IncomeStates.waiting_for_income_description)
        
        await message.answer(
            "<b>Шаг 2/2:</b> Введите описание дохода (необязательно) или отправьте точку (.) для пропуска:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.message(IncomeStates.waiting_for_income_description)
async def income_description_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать описание дохода и сохранить"""
    data = await state.get_data()
    amount = data.get("amount")
    is_regular = data.get("is_regular")
    description = message.text if message.text != "." else ""
    
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            from datetime import date
            
            income = Income(
                user_id=db_user.id,
                name=f"{'Постоянный' if is_regular else 'Внеплановый'} доход",
                amount=amount,
                income_type="regular" if is_regular else "extra",
                frequency="monthly" if is_regular else "once",
                next_date=date.today(),
                description=description
            )
            
            # Также создаем запись в FinanceTransaction для корректного отображения в финансовом отчете
            finance_transaction = FinanceTransaction(
                user_id=db_user.id,
                date=date.today(),
                amount=amount,  # Положительная сумма для дохода
                category="Доход",
                description=f"{'Постоянный' if is_regular else 'Внеплановый'} доход: {description}" if description else f"{'Постоянный' if is_regular else 'Внеплановый'} доход"
            )
            
            session.add(income)
            session.add(finance_transaction)
            await session.commit()
        
        # Формируем сообщение об успехе
        income_type = "постоянный" if is_regular else "внеплановый"
        success_text = f"✅ <b>Доход добавлен!</b>\n\n"
        success_text += f"💰 <b>Сумма:</b> {amount:,.2f} ₽\n"
        success_text += f"📂 <b>Тип:</b> {income_type}\n"
        if description:
            success_text += f"📝 <b>Описание:</b> {description}\n"
        success_text += f"📅 <b>Дата:</b> {date.today().strftime('%d.%m.%Y')}\n\n"
        success_text += f"💡 <b>Примечание:</b> Доход также добавлен в финансовый отчет"
        
        await message.answer(
            success_text,
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при добавлении дохода:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        await state.clear()


@router.callback_query(F.data == "income_list")
async def income_list_handler(cb: types.CallbackQuery) -> None:
    """Показать список доходов"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем все доходы пользователя
            incomes = (await session.execute(
                select(Income).where(Income.user_id == db_user.id).order_by(Income.created_at.desc())
            )).scalars().all()
            
            if not incomes:
                await cb.message.edit_text(
                    "📋 <b>Список доходов</b>\n\n"
                    "У вас пока нет добавленных доходов.",
                    reply_markup=back_main_menu(),
                    parse_mode="HTML"
                )
                await cb.answer()
                return
            
            # Формируем список доходов
            income_text = "📋 <b>Список доходов:</b>\n\n"
            
            for i, income in enumerate(incomes[:20], 1):  # Показываем первые 20
                income_type = "🔄 Постоянный" if income.income_type == "regular" else "💫 Внеплановый"
                income_text += f"{i}. {income_type}\n"
                income_text += f"   💰 {income.amount:,.2f} ₽\n"
                if income.description:
                    income_text += f"   📝 {income.description}\n"
                income_text += f"   📅 {income.created_at.strftime('%d.%m.%Y')}\n\n"
            
            if len(incomes) > 20:
                income_text += f"... и еще {len(incomes) - 20} доходов"
            
            await cb.message.edit_text(
                income_text,
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при получении списка доходов:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


# ===== ОБРАБОТЧИКИ ДЛЯ ФИНАНСОВЫХ ЦЕЛЕЙ =====

@router.callback_query(F.data == "financial_goal_add")
async def financial_goal_add_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать добавление финансовой цели"""
    await cb.message.edit_text(
        "🎯 <b>Добавление финансовой цели</b>\n\n"
        "<b>Шаг 1/5:</b> Введите название цели:",
        parse_mode="HTML"
    )
    await state.set_state(FinancialGoalStates.waiting_for_name)
    await cb.answer()


@router.message(FinancialGoalStates.waiting_for_name)
async def financial_goal_name_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать название финансовой цели"""
    await state.update_data(name=message.text)
    await state.set_state(FinancialGoalStates.waiting_for_target_amount)
    await message.answer(
        "<b>Шаг 2/5:</b> Введите целевую сумму (только число):",
        parse_mode="HTML"
    )


@router.message(FinancialGoalStates.waiting_for_target_amount)
async def financial_goal_target_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать целевую сумму"""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Введите корректную сумму.")
            return
            
        await state.update_data(target_amount=amount)
        await state.set_state(FinancialGoalStates.waiting_for_monthly_percentage)
        await message.answer(
            "<b>Шаг 3/5:</b> Введите процент от месячного дохода для этой цели (1-100):",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.message(FinancialGoalStates.waiting_for_monthly_percentage)
async def financial_goal_percentage_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать процент от месячного дохода"""
    try:
        percentage = int(message.text)
        if percentage < 1 or percentage > 100:
            await message.answer("❌ Процент должен быть от 1 до 100. Введите корректное значение.")
            return
            
        await state.update_data(monthly_percentage=percentage)
        await state.set_state(FinancialGoalStates.waiting_for_deadline)
        await message.answer(
            "<b>Шаг 4/5:</b> Введите срок достижения цели в формате ДД.ММ.ГГГГ (или отправьте точку для пропуска):",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат процента. Введите только число от 1 до 100.")


@router.message(FinancialGoalStates.waiting_for_deadline)
async def financial_goal_deadline_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать срок достижения цели"""
    if message.text == ".":
        await state.update_data(deadline=None)
    else:
        try:
            deadline = datetime.strptime(message.text, "%d.%m.%Y").date()
            await state.update_data(deadline=deadline)
        except ValueError:
            await message.answer("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ или отправьте точку для пропуска.")
            return
    
    await state.set_state(FinancialGoalStates.waiting_for_description)
    await message.answer(
        "<b>Шаг 5/5:</b> Введите описание цели (необязательно) или отправьте точку для пропуска:",
        parse_mode="HTML"
    )


@router.message(FinancialGoalStates.waiting_for_description)
async def financial_goal_description_handler(message: types.Message, state: FSMContext) -> None:
    """Завершить добавление финансовой цели"""
    description = message.text if message.text != "." else None
    await state.update_data(description=description)
    
    data = await state.get_data()
    
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            from decimal import Decimal
            
            financial_goal = FinancialGoal(
                user_id=db_user.id,
                name=data["name"],
                target_amount=Decimal(str(data["target_amount"])),
                current_amount=Decimal("0"),
                monthly_percentage=data["monthly_percentage"],
                deadline=data["deadline"],
                description=data["description"]
            )
            
            session.add(financial_goal)
            await session.commit()
        
        # Формируем сообщение об успехе
        success_text = f"✅ <b>Финансовая цель создана!</b>\n\n"
        success_text += f"🎯 <b>Название:</b> {data['name']}\n"
        success_text += f"💰 <b>Целевая сумма:</b> {data['target_amount']:,.2f} ₽\n"
        success_text += f"📊 <b>Процент от дохода:</b> {data['monthly_percentage']}%\n"
        if data['deadline']:
            success_text += f"📅 <b>Срок:</b> {data['deadline'].strftime('%d.%m.%Y')}\n"
        if data['description']:
            success_text += f"📝 <b>Описание:</b> {data['description']}\n"
        success_text += f"\n💡 <b>Примечание:</b> Цель также отображается в разделе 'Цели'"
        
        await message.answer(
            success_text,
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при создании финансовой цели:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        await state.clear()


@router.callback_query(F.data == "financial_goals_list")
async def financial_goals_list_handler(cb: types.CallbackQuery) -> None:
    """Показать список финансовых целей"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найдена")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем все активные финансовые цели пользователя
            goals = (await session.execute(
                select(FinancialGoal).where(
                    FinancialGoal.user_id == db_user.id,
                    FinancialGoal.is_active.is_(True)
                ).order_by(FinancialGoal.created_at.desc())
            )).scalars().all()
            
            if not goals:
                await cb.message.edit_text(
                    "📋 <b>Финансовые цели</b>\n\n"
                    "У вас пока нет финансовых целей.",
                    reply_markup=back_main_menu(),
                    parse_mode="HTML"
                )
                await cb.answer()
                return
            
            # Формируем список целей
            goals_text = "📋 <b>Ваши финансовые цели:</b>\n\n"
            
            for i, goal in enumerate(goals, 1):
                progress_percentage = (float(goal.current_amount) / float(goal.target_amount)) * 100
                remaining = float(goal.target_amount) - float(goal.current_amount)
                
                goals_text += f"{i}. <b>{goal.name}</b>\n"
                goals_text += f"   💰 Цель: {goal.target_amount:,.2f} ₽\n"
                goals_text += f"   📊 Прогресс: {goal.current_amount:,.2f} ₽ / {goal.target_amount:,.2f} ₽ ({progress_percentage:.1f}%)\n"
                goals_text += f"   🎯 Осталось: {remaining:,.2f} ₽\n"
                goals_text += f"   📈 Процент от дохода: {goal.monthly_percentage}%\n"
                if goal.deadline:
                    goals_text += f"   📅 Срок: {goal.deadline.strftime('%d.%m.%Y')}\n"
                if goal.description:
                    goals_text += f"   📝 {goal.description}\n"
                goals_text += "\n"
            
            await cb.message.edit_text(
                goals_text,
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при получении списка целей:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data == "financial_goal_contribute")
async def financial_goal_contribute_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать пополнение финансовой цели"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем все активные финансовые цели пользователя
            goals = (await session.execute(
                select(FinancialGoal).where(
                    FinancialGoal.user_id == db_user.id,
                    FinancialGoal.is_active.is_(True)
                ).order_by(FinancialGoal.created_at.desc())
            )).scalars().all()
            
            if not goals:
                await cb.message.edit_text(
                    "❌ <b>Нет активных целей</b>\n\n"
                    "Сначала создайте финансовую цель.",
                    reply_markup=back_main_menu(),
                    parse_mode="HTML"
                )
                await cb.answer()
                return
            
            # Создаем клавиатуру с целями
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = []
            for goal in goals:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{goal.name} ({goal.current_amount:,.0f}₽ / {goal.target_amount:,.0f}₽)",
                        callback_data=f"contribute_to_goal:{goal.id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="finance_goals")])
            
            await cb.message.edit_text(
                "💰 <b>Пополнение финансовой цели</b>\n\n"
                "Выберите цель, которую хотите пополнить:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data.startswith("contribute_to_goal:"))
async def contribute_to_goal_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработать выбор цели для пополнения"""
    goal_id = int(cb.data.split(":", 1)[1])
    
    # Сохраняем ID цели в состоянии
    await state.update_data(goal_id=goal_id)
    
    await cb.message.edit_text(
        "💰 <b>Пополнение цели</b>\n\n"
        "Введите сумму для пополнения:",
        parse_mode="HTML"
    )
    
    # Устанавливаем состояние для ожидания суммы
    await state.set_state(FinancialGoalStates.waiting_for_contribution_amount)
    await cb.answer()


@router.message(FinancialGoalStates.waiting_for_contribution_amount)
async def contribution_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать сумму пополнения"""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Введите корректную сумму.")
            return
            
        data = await state.get_data()
        goal_id = data.get("goal_id")
        
        user = message.from_user
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            await state.clear()
            return
        
        try:
            async with session_scope() as session:
                db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
                
                # Получаем цель
                goal = (await session.execute(
                    select(FinancialGoal).where(
                        FinancialGoal.id == goal_id,
                        FinancialGoal.user_id == db_user.id
                    )
                )).scalar_one()
                
                if not goal:
                    await message.answer("❌ Ошибка: цель не найдена")
                    await state.clear()
                    return
                
                # Обновляем текущую сумму
                from decimal import Decimal
                goal.current_amount += Decimal(str(amount))
                
                # Проверяем, достигнута ли цель
                if goal.current_amount >= goal.target_amount:
                    goal.is_active = False  # Цель достигнута
                    await message.answer(
                        f"🎉 <b>Поздравляем! Цель '{goal.name}' достигнута!</b>\n\n"
                        f"💰 Целевая сумма: {goal.target_amount:,.2f} ₽\n"
                        f"💵 Накоплено: {goal.current_amount:,.2f} ₽\n"
                        f"📊 Прогресс: 100%",
                        reply_markup=back_main_menu(),
                        parse_mode="HTML"
                    )
                else:
                    progress_percentage = (float(goal.current_amount) / float(goal.target_amount)) * 100
                    remaining = float(goal.target_amount) - float(goal.current_amount)
                    
                    await message.answer(
                        f"✅ <b>Цель пополнена!</b>\n\n"
                        f"🎯 <b>Цель:</b> {goal.name}\n"
                        f"💰 <b>Пополнено:</b> {amount:,.2f} ₽\n"
                        f"📊 <b>Прогресс:</b> {goal.current_amount:,.2f} ₽ / {goal.target_amount:,.2f} ₽ ({progress_percentage:.1f}%)\n"
                        f"🎯 <b>Осталось:</b> {remaining:,.2f} ₽",
                        reply_markup=back_main_menu(),
                        parse_mode="HTML"
                    )
                
                await session.commit()
                await state.clear()
                
        except Exception as e:
            await message.answer(
                f"❌ <b>Ошибка при пополнении цели:</b>\n{str(e)}",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            await state.clear()
            
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.callback_query(F.data == "financial_goals_progress")
async def financial_goals_progress_handler(cb: types.CallbackQuery) -> None:
    """Показать общий прогресс по финансовым целям"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем все активные финансовые цели пользователя
            goals = (await session.execute(
                select(FinancialGoal).where(
                    FinancialGoal.user_id == db_user.id,
                    FinancialGoal.is_active.is_(True)
                )
            )).scalars().all()
            
            if not goals:
                await cb.message.edit_text(
                    "📊 <b>Прогресс по целям</b>\n\n"
                    "У вас пока нет активных финансовых целей.",
                    reply_markup=back_main_menu(),
                    parse_mode="HTML"
                )
                await cb.answer()
                return
            
            # Рассчитываем общую статистику
            total_target = sum(float(goal.target_amount) for goal in goals)
            total_current = sum(float(goal.current_amount) for goal in goals)
            overall_progress = (total_current / total_target) * 100 if total_target > 0 else 0
            total_remaining = total_target - total_current
            
            # Группируем цели по прогрессу
            completed_goals = [g for g in goals if float(g.current_amount) >= float(g.target_amount)]
            active_goals = [g for g in goals if float(g.current_amount) < float(g.target_amount)]
            
            progress_text = "📊 <b>Общий прогресс по финансовым целям</b>\n\n"
            progress_text += f"🎯 <b>Всего целей:</b> {len(goals)}\n"
            progress_text += f"✅ <b>Завершено:</b> {len(completed_goals)}\n"
            progress_text += f"🔄 <b>Активных:</b> {len(active_goals)}\n\n"
            progress_text += f"💰 <b>Общая цель:</b> {total_target:,.2f} ₽\n"
            progress_text += f"💵 <b>Накоплено:</b> {total_current:,.2f} ₽\n"
            progress_text += f"📊 <b>Общий прогресс:</b> {overall_progress:.1f}%\n"
            progress_text += f"🎯 <b>Осталось накопить:</b> {total_remaining:,.2f} ₽\n\n"
            
            if active_goals:
                progress_text += "<b>Активные цели:</b>\n"
                for goal in active_goals[:5]:  # Показываем первые 5
                    goal_progress = (float(goal.current_amount) / float(goal.target_amount)) * 100
                    progress_text += f"• {goal.name}: {goal_progress:.1f}%\n"
                
                if len(active_goals) > 5:
                    progress_text += f"... и еще {len(active_goals) - 5} целей"
            
            await cb.message.edit_text(
                progress_text,
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при получении прогресса:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data == "finance_categories_groups")
async def finance_categories_groups_handler(cb: types.CallbackQuery) -> None:
    """Показать группировку финансов по основным категориям"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем сводку по группам за последние 30 дней
            from app.services.finance_analytics import get_finance_summary_by_groups, get_group_color
            
            summary = await get_finance_summary_by_groups(session, db_user.id, period_days=30)
            
            if not summary["groups"]:
                await cb.message.edit_text(
                    "📊 <b>Группировка по категориям</b>\n\n"
                    "За последние 30 дней транзакций не найдено.",
                    reply_markup=back_main_menu(),
                    parse_mode="HTML"
                )
                await cb.answer()
                return
            
            # Формируем текст с группировкой
            text = f"📊 <b>Группировка финансов за {summary['period_days']} дней</b>\n\n"
            text += f"💰 <b>Общий доход:</b> {summary['total_income']:,.2f} ₽\n"
            text += f"💸 <b>Общий расход:</b> {summary['total_expenses']:,.2f} ₽\n"
            text += f"⚖️ <b>Баланс:</b> {summary['balance']:,.2f} ₽\n\n"
            
            text += "<b>📈 По основным группам:</b>\n\n"
            
            for group_name, group_data in summary["groups"].items():
                group_color = get_group_color(group_name)
                group_total = group_data["total"]
                group_count = group_data["count"]
                
                # Определяем тип группы (доход/расход)
                if group_total > 0:
                    group_type = "📈 Доходы"
                    group_amount = f"+{group_total:,.2f} ₽"
                else:
                    group_type = "📉 Расходы"
                    group_amount = f"-{abs(group_total):,.2f} ₽"
                
                text += f"{group_color} <b>{group_name}</b>\n"
                text += f"   {group_type}: {group_amount}\n"
                text += f"   📊 Количество: {group_count}\n"
                
                # Показываем топ-3 подкатегории
                if group_data["categories"]:
                    top_categories = sorted(
                        group_data["categories"].items(),
                        key=lambda x: abs(x[1]["total"]),
                        reverse=True
                    )[:3]
                    
                    text += "   📋 Основные категории:\n"
                    for cat_name, cat_data in top_categories:
                        if cat_data["total"] > 0:
                            cat_amount = f"+{cat_data['total']:,.2f} ₽"
                        else:
                            cat_amount = f"-{abs(cat_data['total']):,.2f} ₽"
                        text += f"      • {cat_name}: {cat_amount}\n"
                
                text += "\n"
            
            # Создаем клавиатуру с опциями периода
            keyboard = [
                [
                    InlineKeyboardButton(text="📅 7 дней", callback_data="finance_groups_period_7"),
                    InlineKeyboardButton(text="📅 30 дней", callback_data="finance_groups_period_30"),
                    InlineKeyboardButton(text="📅 90 дней", callback_data="finance_groups_period_90")
                ],
                [
                    InlineKeyboardButton(text="📊 Детальная статистика", callback_data="finance_categories_detailed")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")]
            ]
            
            await cb.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при получении группировки:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data.startswith("finance_groups_period_"))
async def finance_groups_period_handler(cb: types.CallbackQuery) -> None:
    """Обработчик выбора периода для группировки"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найден")
        return
    
    # Извлекаем количество дней из callback_data
    period_str = cb.data.replace("finance_groups_period_", "")
    try:
        period_days = int(period_str)
    except ValueError:
        period_days = 30
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем сводку по группам за выбранный период
            from app.services.finance_analytics import get_finance_summary_by_groups, get_group_color
            
            summary = await get_finance_summary_by_groups(session, db_user.id, period_days=period_days)
            
            if not summary["groups"]:
                await cb.message.edit_text(
                    f"📊 <b>Группировка по категориям</b>\n\n"
                    f"За последние {period_days} дней транзакций не найдено.",
                    reply_markup=back_main_menu(),
                    parse_mode="HTML"
                )
                await cb.answer()
                return
            
            # Формируем текст с группировкой
            text = f"📊 <b>Группировка финансов за {period_days} дней</b>\n\n"
            text += f"💰 <b>Общий доход:</b> {summary['total_income']:,.2f} ₽\n"
            text += f"💸 <b>Общий расход:</b> {summary['total_expenses']:,.2f} ₽\n"
            text += f"⚖️ <b>Баланс:</b> {summary['balance']:,.2f} ₽\n\n"
            
            text += "<b>📈 По основным группам:</b>\n\n"
            
            for group_name, group_data in summary["groups"].items():
                group_color = get_group_color(group_name)
                group_total = group_data["total"]
                group_count = group_data["count"]
                
                # Определяем тип группы (доход/расход)
                if group_total > 0:
                    group_type = "📈 Доходы"
                    group_amount = f"+{group_total:,.2f} ₽"
                else:
                    group_type = "📉 Расходы"
                    group_amount = f"-{abs(group_total):,.2f} ₽"
                
                text += f"{group_color} <b>{group_name}</b>\n"
                text += f"   {group_type}: {group_amount}\n"
                text += f"   📊 Количество: {group_count}\n"
                
                # Показываем топ-3 подкатегории
                if group_data["categories"]:
                    top_categories = sorted(
                        group_data["categories"].items(),
                        key=lambda x: abs(x[1]["total"]),
                        reverse=True
                    )[:3]
                    
                    text += "   📋 Основные категории:\n"
                    for cat_name, cat_data in top_categories:
                        if cat_data["total"] > 0:
                            cat_amount = f"+{cat_data['total']:,.2f} ₽"
                        else:
                            cat_amount = f"-{abs(cat_data['total']):,.2f} ₽"
                        text += f"      • {cat_name}: {cat_amount}\n"
                
                text += "\n"
            
            # Создаем клавиатуру с опциями периода
            keyboard = [
                [
                    InlineKeyboardButton(text="📅 7 дней", callback_data="finance_groups_period_7"),
                    InlineKeyboardButton(text="📅 30 дней", callback_data="finance_groups_period_30"),
                    InlineKeyboardButton(text="📅 90 дней", callback_data="finance_groups_period_90")
                ],
                [
                    InlineKeyboardButton(text="📊 Детальная статистика", callback_data="finance_categories_detailed")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")]
            ]
            
            await cb.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при получении группировки:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data == "finance_categories_detailed")
async def finance_categories_detailed_handler(cb: types.CallbackQuery) -> None:
    """Показать детальную статистику по категориям"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем детальную статистику по категориям за последние 30 дней
            from app.services.finance_analytics import get_category_statistics, get_main_category_group, get_group_color
            
            stats = await get_category_statistics(session, db_user.id, period_days=30)
            
            if not stats["categories"]:
                await cb.message.edit_text(
                    "📊 <b>Детальная статистика по категориям</b>\n\n"
                    "За последние 30 дней транзакций не найдено.",
                    reply_markup=back_main_menu(),
                    parse_mode="HTML"
                )
                await cb.answer()
                return
            
            # Формируем текст с детальной статистикой
            text = f"📊 <b>Детальная статистика за {stats['period_days']} дней</b>\n\n"
            text += f"💰 <b>Общий доход:</b> {stats['total_income']:,.2f} ₽\n"
            text += f"💸 <b>Общий расход:</b> {stats['total_expenses']:,.2f} ₽\n"
            text += f"⚖️ <b>Баланс:</b> {stats['balance']:,.2f} ₽\n\n"
            
            text += "<b>📋 По категориям:</b>\n\n"
            
            for category_name, category_data in stats["categories"].items():
                main_group = category_data["main_group"]
                group_color = get_group_color(main_group)
                category_total = category_data["total"]
                category_count = category_data["count"]
                
                # Определяем тип категории (доход/расход)
                if category_total > 0:
                    category_type = "📈 Доходы"
                    category_amount = f"+{category_total:,.2f} ₽"
                else:
                    category_type = "📉 Расходы"
                    category_amount = f"-{abs(category_total):,.2f} ₽"
                
                text += f"{group_color} <b>{category_name}</b>\n"
                text += f"   📂 Группа: {main_group}\n"
                text += f"   {category_type}: {category_amount}\n"
                text += f"   📊 Количество: {category_count}\n\n"
            
            # Создаем клавиатуру
            keyboard = [
                [
                    InlineKeyboardButton(text="📅 7 дней", callback_data="finance_detailed_period_7"),
                    InlineKeyboardButton(text="📅 30 дней", callback_data="finance_detailed_period_30"),
                    InlineKeyboardButton(text="📅 90 дней", callback_data="finance_detailed_period_90")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="finance_categories_groups")]
            ]
            
            await cb.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при получении статистики:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.message(Command("test_finance_todo"))
async def test_finance_todo_creation(message: types.Message) -> None:
    """Тестирование создания задач To-Do для финансовых обязательств"""
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )).scalar_one()
            
            # Создаем задачи для финансовых обязательств
            await create_todo_for_financial_obligations(session, db_user.id)
            
            await message.answer(
                "✅ <b>Тест создания задач To-Do для финансовых обязательств</b>\n\n"
                "Задачи для финансовых обязательств, срок которых наступил сегодня, "
                "были созданы в вашем To-Do списке.\n\n"
                "Проверьте раздел To-Do для просмотра созданных задач.",
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при тестировании:</b>\n{str(e)}",
            parse_mode="HTML"
        )
