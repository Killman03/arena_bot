from __future__ import annotations

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.db.session import session_scope
from app.db.models import User
from sqlalchemy import select
from app.services.daily_reminders import (
    daily_reminder_keyboard, 
    perfect_day_keyboard,
    generate_perfect_day_plan,
    create_todo_from_perfect_day
)
from app.keyboards.common import back_main_menu
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


class QuickTodoStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()


class PerfectDayStates(StatesGroup):
    waiting_confirmation = State()


@router.callback_query(F.data == "quick_add_todo")
async def quick_add_todo_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Быстрое добавление задачи"""
    await state.set_state(QuickTodoStates.waiting_title)
    await cb.message.edit_text(
        "📝 <b>Быстрое добавление задачи</b>\n\n"
        "Введите название задачи:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(QuickTodoStates.waiting_title)
async def quick_todo_title_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка названия быстрой задачи"""
    if len(message.text) > 500:
        await message.answer("❌ Название слишком длинное. Максимум 500 символов.")
        return
    
    await state.update_data(title=message.text)
    await state.set_state(QuickTodoStates.waiting_description)
    
    await message.answer(
        "📝 <b>Добавление задачи</b>\n\n"
        "Введите описание задачи (или '-' чтобы пропустить):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(QuickTodoStates.waiting_description)
async def quick_todo_description_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка описания быстрой задачи"""
    desc = (message.text or "").strip()
    if desc == "-":
        desc = None
    
    data = await state.get_data()
    title = data.get("title")
    
    if not title:
        await message.answer("❌ Ошибка: название задачи не найдено.")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )).scalar_one()
            
            from app.db.models.todo import Todo
            from datetime import date
            
            new_todo = Todo(
                user_id=db_user.id,
                title=title,
                description=desc,
                due_date=date.today(),
                priority="medium",
                is_daily=False
            )
            
            session.add(new_todo)
            await session.commit()
            
            await message.answer(
                "✅ <b>Задача добавлена!</b>\n\n"
                f"📝 <b>{title}</b>\n"
                f"📅 Дата: сегодня\n"
                f"🎯 Приоритет: средний\n\n"
                "Задача добавлена в ваш To-Do список.",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении задачи: {str(e)}")
    
    await state.clear()


@router.callback_query(F.data == "perfect_day_plan")
async def perfect_day_menu(cb: types.CallbackQuery) -> None:
    """Меню планирования идеального дня"""
    await cb.message.edit_text(
        "⚔️ <b>ПРИКАЗ ЛАНИСТЫ</b>\n\n"
        "Готов получить план тренировок на завтра, гладиатор?\n\n"
        "🎯 <b>Что тебя ждет:</b>\n"
        "• Персональный план на основе твоих целей\n"
        "• Учет запланированных задач дня\n"
        "• Воинственная мотивация и дисциплина\n"
        "• Конкретные временные рамки\n\n"
        "Выбери действие, воин:",
        reply_markup=perfect_day_keyboard(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "create_perfect_day")
async def create_perfect_day_handler(cb: types.CallbackQuery) -> None:
    """Создание плана идеального дня"""
    # Сразу отвечаем на callback query, чтобы избежать ошибки "query is too old"
    await cb.answer()
    
    await cb.message.edit_text(
        "⚔️ <b>ЛАНИСТА СОСТАВЛЯЕТ ПЛАН</b>\n\n"
        "⏳ Анализирую твои цели и задачи...\n"
        "🔍 Изучаю твою мотивацию...\n"
        "💪 Готовлю план тренировок...\n"
        "Это может занять несколько секунд.",
        parse_mode="HTML"
    )
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == cb.from_user.id)
            )).scalar_one()
            
            # Генерируем план
            plan = await generate_perfect_day_plan(db_user.id, session)
            
            # Отправляем план
            await cb.message.edit_text(
                plan,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="⚔️ Создать задачи в To-Do", callback_data="convert_plan_to_todos"),
                        InlineKeyboardButton(text="🔄 Новый план", callback_data="create_perfect_day")
                    ],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="perfect_day_plan")]
                ]),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при создании плана</b>\n\n"
            f"Не удалось сгенерировать план: {str(e)}\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "convert_plan_to_todos")
async def convert_plan_to_todos_handler(cb: types.CallbackQuery) -> None:
    """Конвертация плана в задачи To-Do"""
    # Сразу отвечаем на callback query, чтобы избежать ошибки "query is too old"
    await cb.answer()
    
    try:
        # Получаем текст плана из сообщения
        plan_text = cb.message.text
        
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == cb.from_user.id)
            )).scalar_one()
            
            # Создаем задачи из плана
            success = await create_todo_from_perfect_day(db_user.id, plan_text, session)
            
            if success:
                await cb.message.edit_text(
                    "⚔️ <b>ПЛАН ПРИНЯТ К ИСПОЛНЕНИЮ!</b>\n\n"
                    "Все пункты плана добавлены в твой список задач.\n\n"
                    "Теперь ты можешь:\n"
                    "• Отмечать выполненные тренировки\n"
                    "• Корректировать приоритеты\n"
                    "• Добавлять детали к задачам\n\n"
                    "💪 Начни с самого важного дела, гладиатор!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝 Открыть To-Do", callback_data="menu_todo")],
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="perfect_day_plan")]
                    ]),
                    parse_mode="HTML"
                )
            else:
                await cb.message.edit_text(
                    "⚠️ <b>Не удалось создать задачи</b>\n\n"
                    "Возможно, план не содержит подходящих пунктов для конвертации.\n\n"
                    "Попробуйте создать новый план или добавьте задачи вручную.",
                    reply_markup=back_main_menu(),
                    parse_mode="HTML"
                )
                
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка при конвертации</b>\n\n"
            f"Не удалось создать задачи: {str(e)}",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "day_templates")
async def day_templates_handler(cb: types.CallbackQuery) -> None:
    """Показать шаблоны дня"""
    templates_text = (
        "⚔️ <b>ШАБЛОНЫ ТРЕНИРОВОК ГЛАДИАТОРА</b>\n\n"
        "🎯 <b>Классический день воина:</b>\n"
        "• 6:00 - Пробуждение и утренняя зарядка\n"
        "• 6:30 - Омовение и завтрак\n"
        "• 7:00 - Планирование дня и постановка целей\n"
        "• 8:00 - Самая важная битва дня\n"
        "• 10:00 - Короткий отдых и восстановление сил\n"
        "• 10:15 - Вторая важная задача\n"
        "• 12:00 - Обед и восстановление энергии\n"
        "• 13:00 - Работа над долгосрочными проектами\n"
        "• 15:00 - Перерыв для силы духа\n"
        "• 15:15 - Творческие тренировки\n"
        "• 17:00 - Подведение итогов дня\n"
        "• 18:00 - Физические тренировки\n"
        "• 19:00 - Ужин и восстановление\n"
        "• 20:00 - Чтение и развитие ума\n"
        "• 21:00 - Подготовка к отдыху\n"
        "• 22:00 - Сон для восстановления сил\n\n"
        "💪 <b>Совет ланисты:</b> Адаптируй под свой ритм, но сохраняй дисциплину!"
    )
    
    await cb.message.edit_text(
        templates_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Создать персональный план", callback_data="create_perfect_day")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="perfect_day_plan")]
        ]),
        parse_mode="HTML"
    )
    await cb.answer()



