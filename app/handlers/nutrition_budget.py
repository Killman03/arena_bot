from __future__ import annotations

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from decimal import Decimal

from app.db.session import session_scope
from app.db.models import User, Income
from app.keyboards.common import back_main_menu
from app.services.finance_analytics import get_finance_summary

router = Router()


class NutritionBudgetStates(StatesGroup):
    """Состояния для настройки бюджета питания"""
    waiting_for_budget_type = State()
    waiting_for_percentage = State()
    waiting_for_fixed_amount = State()


@router.callback_query(F.data == "nutrition_budget")
async def nutrition_budget_menu(cb: types.CallbackQuery) -> None:
    """Показать меню настройки бюджета питания"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем текущие настройки бюджета
            current_budget_text = ""
            if db_user.food_budget_type == "percentage_income" and db_user.food_budget_percentage:
                current_budget_text = f"\n\n<b>Текущие настройки:</b>\n📊 {db_user.food_budget_percentage}% от месячного дохода"
            elif db_user.food_budget_type == "fixed_amount" and db_user.food_budget_amount:
                current_budget_text = f"\n\n<b>Текущие настройки:</b>\n💰 {db_user.food_budget_amount:,.2f} ₽ в месяц"
            
            # Получаем финансовую сводку для расчета рекомендаций
            summary = await get_finance_summary(session, db_user.id)
            
            budget_text = f"""💰 <b>Настройка бюджета питания</b>

Настройте лимит трат на еду, который будет учитываться при планировании питания.

💵 <b>Ваш месячный доход:</b> {summary['monthly_income']:,.2f} ₽
📉 <b>Текущие расходы:</b> {summary['monthly_expenses']:,.2f} ₽{current_budget_text}

Выберите тип бюджета:"""

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📊 Процент от дохода", callback_data="budget_type_percentage"),
                        InlineKeyboardButton(text="💰 Фиксированная сумма", callback_data="budget_type_fixed")
                    ],
                    [
                        InlineKeyboardButton(text="🗑️ Сбросить настройки", callback_data="budget_reset"),
                        InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_nutrition")
                    ]
                ]
            )
            
            await cb.message.edit_text(budget_text, reply_markup=keyboard, parse_mode="HTML")
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data == "budget_type_percentage")
async def budget_type_percentage(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Настройка бюджета как процент от дохода"""
    await cb.message.edit_text(
        "📊 <b>Процент от месячного дохода</b>\n\n"
        "Введите процент от вашего месячного дохода, который вы готовы тратить на питание.\n\n"
        "<b>Рекомендуемые значения:</b>\n"
        "• 15-20% - экономный план\n"
        "• 20-25% - оптимальный план\n"
        "• 25-30% - комфортный план\n\n"
        "Введите процент (от 5 до 50):",
        parse_mode="HTML"
    )
    await state.set_state(NutritionBudgetStates.waiting_for_percentage)
    await cb.answer()


@router.message(NutritionBudgetStates.waiting_for_percentage)
async def process_percentage(message: types.Message, state: FSMContext) -> None:
    """Обработать процент для бюджета питания"""
    try:
        percentage = int(message.text)
        if percentage < 5 or percentage > 50:
            await message.answer("❌ Процент должен быть от 5 до 50. Введите корректное значение.")
            return
        
        user = message.from_user
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            await state.clear()
            return
        
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Сохраняем настройки
            db_user.food_budget_type = "percentage_income"
            db_user.food_budget_percentage = percentage
            db_user.food_budget_amount = None  # Очищаем фиксированную сумму
            
            await session.commit()
            
            # Рассчитываем примерную сумму
            summary = await get_finance_summary(session, db_user.id)
            estimated_amount = summary['monthly_income'] * percentage / 100
            
            success_text = f"""✅ <b>Бюджет питания настроен!</b>

📊 <b>Тип:</b> Процент от дохода
📈 <b>Процент:</b> {percentage}%
💰 <b>Примерная сумма:</b> {estimated_amount:,.2f} ₽/месяц

Теперь ИИ будет учитывать этот бюджет при планировании питания."""

            await message.answer(
                success_text,
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат. Введите только число от 5 до 50.")
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при сохранении настроек:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        await state.clear()


@router.callback_query(F.data == "budget_type_fixed")
async def budget_type_fixed(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Настройка фиксированного бюджета"""
    await cb.message.edit_text(
        "💰 <b>Фиксированная сумма</b>\n\n"
        "Введите фиксированную сумму, которую вы готовы тратить на питание в месяц.\n\n"
        "<b>Примерные ориентиры:</b>\n"
        "• 8,000-12,000 ₽ - базовое питание\n"
        "• 12,000-18,000 ₽ - сбалансированное питание\n"
        "• 18,000-25,000 ₽ - разнообразное питание\n\n"
        "Введите сумму в рублях:",
        parse_mode="HTML"
    )
    await state.set_state(NutritionBudgetStates.waiting_for_fixed_amount)
    await cb.answer()


@router.message(NutritionBudgetStates.waiting_for_fixed_amount)
async def process_fixed_amount(message: types.Message, state: FSMContext) -> None:
    """Обработать фиксированную сумму для бюджета питания"""
    try:
        amount = float(message.text)
        if amount < 1000 or amount > 100000:
            await message.answer("❌ Сумма должна быть от 1,000 до 100,000 рублей. Введите корректное значение.")
            return
        
        user = message.from_user
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            await state.clear()
            return
        
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Сохраняем настройки
            db_user.food_budget_type = "fixed_amount"
            db_user.food_budget_amount = Decimal(str(amount))
            db_user.food_budget_percentage = None  # Очищаем процент
            
            await session.commit()
            
            # Рассчитываем процент от дохода для справки
            summary = await get_finance_summary(session, db_user.id)
            percentage_of_income = (amount / summary['monthly_income'] * 100) if summary['monthly_income'] > 0 else 0
            
            success_text = f"""✅ <b>Бюджет питания настроен!</b>

💰 <b>Тип:</b> Фиксированная сумма
📊 <b>Сумма:</b> {amount:,.2f} ₽/месяц
📈 <b>Процент от дохода:</b> {percentage_of_income:.1f}%

Теперь ИИ будет учитывать этот бюджет при планировании питания."""

            await message.answer(
                success_text,
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите только число.")
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при сохранении настроек:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        await state.clear()


@router.callback_query(F.data == "budget_reset")
async def budget_reset(cb: types.CallbackQuery) -> None:
    """Сбросить настройки бюджета питания"""
    user = cb.from_user
    if not user:
        await cb.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Сбрасываем настройки
            db_user.food_budget_type = None
            db_user.food_budget_percentage = None
            db_user.food_budget_amount = None
            
            await session.commit()
            
            await cb.message.edit_text(
                "✅ <b>Настройки бюджета питания сброшены</b>\n\n"
                "Теперь ИИ будет планировать питание без учета бюджетных ограничений.",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при сбросе настроек:</b>\n{str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()


async def get_user_food_budget(session, user_id: int) -> dict:
    """Получить настройки бюджета питания пользователя"""
    db_user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    
    if not db_user.food_budget_type:
        return {"type": None, "amount": None, "description": "без ограничений"}
    
    if db_user.food_budget_type == "percentage_income":
        # Рассчитываем сумму на основе дохода
        summary = await get_finance_summary(session, user_id)
        amount = summary['monthly_income'] * db_user.food_budget_percentage / 100
        return {
            "type": "percentage",
            "percentage": db_user.food_budget_percentage,
            "amount": amount,
            "description": f"{db_user.food_budget_percentage}% от дохода (~{amount:,.0f} ₽/месяц)"
        }
    
    elif db_user.food_budget_type == "fixed_amount":
        return {
            "type": "fixed",
            "amount": float(db_user.food_budget_amount),
            "description": f"{db_user.food_budget_amount:,.0f} ₽/месяц"
        }
    
    return {"type": None, "amount": None, "description": "без ограничений"}
