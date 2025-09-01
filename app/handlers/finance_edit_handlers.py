from __future__ import annotations

from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import session_scope
from app.db.models import User, Creditor, Debtor
from app.keyboards.common import back_main_menu
from app.services.finance_reminders import send_finance_reminders_for_user
from app.handlers.finance_management import CreditorStates, DebtorStates

router = Router()


@router.callback_query(F.data.startswith("creditor_edit:"))
async def creditor_edit_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать редактирование кредитора"""
    creditor_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        creditor = await session.get(Creditor, creditor_id)
        if not creditor:
            await cb.answer("Кредитор не найден")
            return
        
        # Сохраняем ID кредитора в состоянии
        await state.update_data(creditor_id=creditor_id)
        await state.set_state(CreditorStates.waiting_for_name)
        
        await cb.message.edit_text(
            f"✏️ <b>Редактирование кредитора</b>\n\n"
            f"👤 <b>Текущее имя:</b> {creditor.name}\n"
            f"💰 <b>Текущая сумма:</b> {float(creditor.amount):,.2f} ₽\n"
            f"📅 <b>Текущая дата:</b> {creditor.due_date.strftime('%d.%m.%Y')}\n"
            f"📝 <b>Текущее описание:</b> {creditor.description or 'Не указано'}\n\n"
            f"<b>Шаг 1/4:</b> Введите новое имя кредитора:",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data.startswith("debtor_edit:"))
async def debtor_edit_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать редактирование должника"""
    debtor_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        debtor = await session.get(Debtor, debtor_id)
        if not debtor:
            await cb.answer("Должник не найден")
            return
        
        # Сохраняем ID должника в состоянии
        await state.update_data(debtor_id=debtor_id)
        await state.set_state(DebtorStates.waiting_for_name)
        
        await cb.message.edit_text(
            f"✏️ <b>Редактирование должника</b>\n\n"
            f"👤 <b>Текущее имя:</b> {debtor.name}\n"
            f"💰 <b>Текущая сумма:</b> {float(debtor.amount):,.2f} ₽\n"
            f"📅 <b>Текущая дата:</b> {debtor.due_date.strftime('%d.%m.%Y')}\n"
            f"📝 <b>Текущее описание:</b> {debtor.description or 'Не указано'}\n\n"
            f"<b>Шаг 1/4:</b> Введите новое имя должника:",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


# Обработчики для редактирования кредитора (переиспользуем существующие состояния)
@router.message(CreditorStates.waiting_for_name)
async def creditor_edit_name_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать новое имя кредитора при редактировании"""
    data = await state.get_data()
    creditor_id = data.get("creditor_id")
    
    if not creditor_id:
        await message.answer("❌ Ошибка: ID кредитора не найден")
        await state.clear()
        return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя должно содержать минимум 2 символа. Попробуйте еще раз.")
        return
    
    await state.update_data(name=name)
    await state.set_state(CreditorStates.waiting_for_amount)
    
    await message.answer(
        "<b>Шаг 2/4:</b> Введите новую сумму долга (только число):",
        parse_mode="HTML"
    )


@router.message(CreditorStates.waiting_for_amount)
async def creditor_edit_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать новую сумму кредитора при редактировании"""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Введите корректную сумму.")
            return
        
        await state.update_data(amount=amount)
        await state.set_state(CreditorStates.waiting_for_due_date)
        
        await message.answer(
            "<b>Шаг 3/4:</b> Введите новую дату выплаты в формате ДД.ММ.ГГГГ:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.message(CreditorStates.waiting_for_due_date)
async def creditor_edit_due_date_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать новую дату кредитора при редактировании"""
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        await state.update_data(due_date=due_date)
        await state.set_state(CreditorStates.waiting_for_description)
        
        await message.answer(
            "<b>Шаг 4/4:</b> Введите новое описание (необязательно) или отправьте точку (.) для пропуска:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ")


@router.message(CreditorStates.waiting_for_description)
async def creditor_edit_description_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать новое описание кредитора при редактировании и сохранить"""
    data = await state.get_data()
    creditor_id = data.get("creditor_id")
    name = data.get("name")
    amount = data.get("amount")
    due_date = data.get("due_date")
    description = message.text if message.text != "." else ""
    
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем кредитора для обновления
            creditor = await session.get(Creditor, creditor_id)
            if not creditor or creditor.user_id != db_user.id:
                await message.answer("❌ Кредитор не найден или у вас нет прав на его редактирование")
                await state.clear()
                return
            
            # Обновляем данные кредитора
            creditor.name = name
            creditor.amount = amount
            creditor.due_date = due_date
            creditor.description = description
            creditor.updated_at = datetime.now()
            
            await session.commit()
            
            await message.answer(
                f"✅ <b>Кредитор успешно обновлен!</b>\n\n"
                f"👤 <b>Имя:</b> {name}\n"
                f"💰 <b>Сумма:</b> {amount:,.2f} ₽\n"
                f"📅 <b>Дата выплаты:</b> {due_date.strftime('%d.%m.%Y')}\n"
                f"📝 <b>Описание:</b> {description or 'Не указано'}",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при обновлении кредитора:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await state.clear()


# Обработчики для редактирования должника (переиспользуем существующие состояния)
@router.message(DebtorStates.waiting_for_name)
async def debtor_edit_name_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать новое имя должника при редактировании"""
    data = await state.get_data()
    debtor_id = data.get("debtor_id")
    
    if not debtor_id:
        await message.answer("❌ Ошибка: ID должника не найден")
        await state.clear()
        return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Имя должно содержать минимум 2 символа. Попробуйте еще раз.")
        return
    
    await state.update_data(name=name)
    await state.set_state(DebtorStates.waiting_for_amount)
    
    await message.answer(
        "<b>Шаг 2/4:</b> Введите новую сумму долга (только число):",
        parse_mode="HTML"
    )


@router.message(DebtorStates.waiting_for_amount)
async def debtor_edit_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать новую сумму должника при редактировании"""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля. Введите корректную сумму.")
            return
        
        await state.update_data(amount=amount)
        await state.set_state(DebtorStates.waiting_for_due_date)
        
        await message.answer(
            "<b>Шаг 3/4:</b> Введите новую дату выплаты в формате ДД.ММ.ГГГГ:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")


@router.message(DebtorStates.waiting_for_due_date)
async def debtor_edit_due_date_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать новую дату должника при редактировании"""
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        await state.update_data(due_date=due_date)
        await state.set_state(DebtorStates.waiting_for_description)
        
        await message.answer(
            "<b>Шаг 4/4:</b> Введите новое описание (необязательно) или отправьте точку (.) для пропуска:",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ")


@router.message(DebtorStates.waiting_for_description)
async def debtor_edit_description_handler(message: types.Message, state: FSMContext) -> None:
    """Обработать новое описание должника при редактировании и сохранить"""
    data = await state.get_data()
    debtor_id = data.get("debtor_id")
    name = data.get("name")
    amount = data.get("amount")
    due_date = data.get("due_date")
    description = message.text if message.text != "." else ""
    
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем должника для обновления
            debtor = await session.get(Debtor, debtor_id)
            if not debtor or debtor.user_id != db_user.id:
                await message.answer("❌ Должник не найден или у вас нет прав на его редактирование")
                await state.clear()
                return
            
            # Обновляем данные должника
            debtor.name = name
            debtor.amount = amount
            debtor.due_date = due_date
            debtor.description = description
            debtor.updated_at = datetime.now()
            
            await session.commit()
            
            await message.answer(
                f"✅ <b>Должник успешно обновлен!</b>\n\n"
                f"👤 <b>Имя:</b> {name}\n"
                f"💰 <b>Сумма:</b> {amount:,.2f} ₽\n"
                f"📅 <b>Дата выплаты:</b> {due_date.strftime('%d.%m.%Y')}\n"
                f"📝 <b>Описание:</b> {description or 'Не указано'}",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при обновлении должника:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await state.clear()


@router.message(Command("test_finance_reminders"))
async def test_finance_reminders(message: types.Message) -> None:
    """Тестирование финансовых уведомлений"""
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Отправляем тестовое финансовое уведомление
            await send_finance_reminders_for_user(session, db_user.id)
            
            await message.answer(
                "✅ <b>Тестовое финансовое уведомление отправлено!</b>\n\n"
                "Проверьте, получили ли вы уведомление о ваших финансовых обязательствах.",
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при тестировании:</b>\n{str(e)}",
            parse_mode="HTML"
        )
