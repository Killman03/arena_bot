from __future__ import annotations

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.db.session import session_scope
from app.db.models import User
from app.keyboards.common import quick_actions_menu, back_main_menu
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

router = Router()


class QuickQuoteStates(StatesGroup):
    waiting_quote = State()
    waiting_author = State()


class QuickGoalStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()


class QuickThoughtStates(StatesGroup):
    waiting_thought = State()


class QuickTodoStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()


class QuickExpenseStates(StatesGroup):
    waiting_amount = State()
    waiting_category = State()


class QuickReminderStates(StatesGroup):
    waiting_text = State()
    waiting_time = State()
    waiting_custom_time = State()


@router.callback_query(F.data == "quick_actions")
async def quick_actions_menu_handler(cb: types.CallbackQuery) -> None:
    """Показать меню быстрых действий"""
    await cb.message.edit_text(
        "🚀 <b>Быстрые действия</b>\n\n"
        "Выберите действие, которое хотите выполнить быстро:",
        reply_markup=quick_actions_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "quick_add_quote")
async def quick_add_quote_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать быстрое добавление цитаты"""
    await state.set_state(QuickQuoteStates.waiting_quote)
    await cb.message.edit_text(
        "📝 <b>Быстрое добавление цитаты</b>\n\n"
        "Введите текст цитаты:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(QuickQuoteStates.waiting_quote)
async def quick_quote_text_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка текста цитаты"""
    if len(message.text) > 1000:
        await message.answer("❌ Цитата слишком длинная. Максимум 1000 символов.")
        return
    
    await state.update_data(quote=message.text)
    await state.set_state(QuickQuoteStates.waiting_author)
    
    await message.answer(
        "📝 <b>Добавление цитаты</b>\n\n"
        "Введите автора цитаты (или '-' чтобы пропустить):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(QuickQuoteStates.waiting_author)
async def quick_quote_author_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка автора цитаты"""
    author = (message.text or "").strip()
    if author == "-":
        author = None
    
    data = await state.get_data()
    quote = data.get("quote")
    
    if not quote:
        await message.answer("❌ Ошибка: текст цитаты не найден.")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )).scalar_one()
            
            from app.db.models.book import BookQuote
            from datetime import datetime
            
            new_quote = BookQuote(
                user_id=db_user.id,
                quote=quote,
                author=author,
                created_at=datetime.now()
            )
            
            session.add(new_quote)
            await session.commit()
            
            await message.answer(
                "✅ <b>Цитата добавлена!</b>\n\n"
                f"📝 <b>Цитата:</b>\n{quote}\n\n"
                f"👤 <b>Автор:</b> {author or 'Не указан'}\n\n"
                "Цитата сохранена в вашей библиотеке.",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении цитаты: {str(e)}")
    
    await state.clear()


@router.callback_query(F.data == "quick_add_goal")
async def quick_add_goal_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать быстрое добавление цели"""
    await state.set_state(QuickGoalStates.waiting_title)
    await cb.message.edit_text(
        "🎯 <b>Быстрое добавление цели</b>\n\n"
        "Введите название цели:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(QuickGoalStates.waiting_title)
async def quick_goal_title_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка названия цели"""
    if len(message.text) > 500:
        await message.answer("❌ Название слишком длинное. Максимум 500 символов.")
        return
    
    await state.update_data(title=message.text)
    await state.set_state(QuickGoalStates.waiting_description)
    
    await message.answer(
        "🎯 <b>Добавление цели</b>\n\n"
        "Введите описание цели (или '-' чтобы пропустить):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(QuickGoalStates.waiting_description)
async def quick_goal_description_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка описания цели"""
    desc = (message.text or "").strip()
    if desc == "-":
        desc = None
    
    data = await state.get_data()
    title = data.get("title")
    
    if not title:
        await message.answer("❌ Ошибка: название цели не найдено.")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )).scalar_one()
            
            from app.db.models.goal import Goal, GoalStatus, GoalScope
            from datetime import date
            
            new_goal = Goal(
                user_id=db_user.id,
                title=title,
                description=desc,
                status=GoalStatus.active,
                scope=GoalScope.personal,
                created_at=date.today()
            )
            
            session.add(new_goal)
            await session.commit()
            
            await message.answer(
                "✅ <b>Цель добавлена!</b>\n\n"
                f"🎯 <b>{title}</b>\n"
                f"📝 <b>Описание:</b> {desc or 'Не указано'}\n"
                f"📅 <b>Дата создания:</b> {date.today().strftime('%d.%m.%Y')}\n\n"
                "Цель добавлена в ваш список целей.",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении цели: {str(e)}")
    
    await state.clear()


@router.callback_query(F.data == "quick_add_thought")
async def quick_add_thought_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать быстрое добавление мысли"""
    await state.set_state(QuickThoughtStates.waiting_thought)
    await cb.message.edit_text(
        "📚 <b>Быстрое добавление мысли</b>\n\n"
        "Введите вашу мысль или идею:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(QuickThoughtStates.waiting_thought)
async def quick_thought_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка мысли"""
    if len(message.text) > 2000:
        await message.answer("❌ Мысль слишком длинная. Максимум 2000 символов.")
        return
    
    thought = message.text
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )).scalar_one()
            
            from app.db.models.book import BookThought
            from datetime import datetime
            
            new_thought = BookThought(
                user_id=db_user.id,
                thought=thought,
                created_at=datetime.now()
            )
            
            session.add(new_thought)
            await session.commit()
            
            await message.answer(
                "✅ <b>Мысль добавлена!</b>\n\n"
                f"📚 <b>Ваша мысль:</b>\n{thought}\n\n"
                f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                "Мысль сохранена в вашей библиотеке.",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении мысли: {str(e)}")
    
    await state.clear()


@router.callback_query(F.data == "quick_add_expense")
async def quick_add_expense_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать быстрое добавление расхода"""
    await state.set_state(QuickExpenseStates.waiting_amount)
    await cb.message.edit_text(
        "💰 <b>Быстрое добавление расхода</b>\n\n"
        "Введите сумму расхода (например: 1500 или 1500.50):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(QuickExpenseStates.waiting_amount)
async def quick_expense_amount_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка суммы расхода"""
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше нуля.")
            return
        
        await state.update_data(amount=amount)
        await state.set_state(QuickExpenseStates.waiting_category)
        
        # Показываем меню категорий
        categories_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🛒 Покупки", callback_data="quick_expense_category_purchases"),
                    InlineKeyboardButton(text="🍽️ Питание", callback_data="quick_expense_category_food")
                ],
                [
                    InlineKeyboardButton(text="🚗 Транспорт", callback_data="quick_expense_category_transport"),
                    InlineKeyboardButton(text="🏠 Коммунальные", callback_data="quick_expense_category_utilities")
                ],
                [
                    InlineKeyboardButton(text="💊 Здоровье", callback_data="quick_expense_category_health"),
                    InlineKeyboardButton(text="🎭 Развлечения", callback_data="quick_expense_category_entertainment")
                ],
                [
                    InlineKeyboardButton(text="📱 Связь", callback_data="quick_expense_category_communication"),
                    InlineKeyboardButton(text="👕 Одежда", callback_data="quick_expense_category_clothing")
                ],
                [
                    InlineKeyboardButton(text="📚 Образование", callback_data="quick_expense_category_education"),
                    InlineKeyboardButton(text="🏦 Банковские", callback_data="quick_expense_category_banking")
                ],
                [
                    InlineKeyboardButton(text="🔧 Прочее", callback_data="quick_expense_category_other")
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
                ]
            ]
        )
        
        await message.answer(
            f"💰 <b>Сумма расхода:</b> {amount:,.2f} ₽\n\n"
            "Выберите категорию расхода:",
            reply_markup=categories_keyboard,
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число (например: 1500 или 1500.50)")


@router.callback_query(F.data.startswith("quick_expense_category_"))
async def quick_expense_category_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора категории расхода"""
    category = cb.data.replace("quick_expense_category_", "")
    
    data = await state.get_data()
    amount = data.get("amount")
    
    if not amount:
        await cb.message.edit_text("❌ Ошибка: сумма расхода не найдена.")
        await state.clear()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == cb.from_user.id)
            )).scalar_one()
            
            from app.db.models.finance import FinanceTransaction
            from datetime import datetime
            
            new_expense = FinanceTransaction(
                user_id=db_user.id,
                amount=-amount,  # Отрицательная сумма для расхода
                category=category,
                date=datetime.now().date(),
                description=f"Быстрый расход - {category}"
            )
            
            session.add(new_expense)
            await session.commit()
            
            category_names = {
                "purchases": "🛒 Покупки",
                "food": "🍽️ Питание",
                "transport": "🚗 Транспорт",
                "utilities": "🏠 Коммунальные",
                "health": "💊 Здоровье",
                "entertainment": "🎭 Развлечения",
                "communication": "📱 Связь",
                "clothing": "👕 Одежда",
                "education": "📚 Образование",
                "banking": "🏦 Банковские",
                "other": "🔧 Прочее"
            }
            
            category_display = category_names.get(category, category)
            
            await cb.message.edit_text(
                "✅ <b>Расход добавлен!</b>\n\n"
                f"💰 <b>Сумма:</b> {amount:,.2f} ₽\n"
                f"📂 <b>Категория:</b> {category_display}\n"
                f"📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y')}\n\n"
                "Расход записан в ваши финансы.",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(f"❌ Ошибка при добавлении расхода: {str(e)}")
    
    await state.clear()
    await cb.answer()


@router.callback_query(F.data == "quick_add_reminder")
async def quick_add_reminder_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать быстрое создание напоминания"""
    await state.set_state(QuickReminderStates.waiting_text)
    await cb.message.edit_text(
        "⏰ <b>Быстрое создание напоминания</b>\n\n"
        "Введите текст напоминания:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(QuickReminderStates.waiting_text)
async def quick_reminder_text_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка текста напоминания"""
    if len(message.text) > 500:
        await message.answer("❌ Текст напоминания слишком длинный. Максимум 500 символов.")
        return
    
    await state.update_data(text=message.text)
    await state.set_state(QuickReminderStates.waiting_time)
    
    # Показываем меню времени
    time_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏰ Через 1 час", callback_data="reminder_time_1h"),
                InlineKeyboardButton(text="⏰ Через 3 часа", callback_data="reminder_time_3h")
            ],
            [
                InlineKeyboardButton(text="⏰ Через 6 часов", callback_data="reminder_time_6h"),
                InlineKeyboardButton(text="⏰ Через 12 часов", callback_data="reminder_time_12h")
            ],
            [
                InlineKeyboardButton(text="⏰ Завтра утром", callback_data="reminder_time_tomorrow"),
                InlineKeyboardButton(text="⏰ Через неделю", callback_data="reminder_time_week")
            ],
            [
                InlineKeyboardButton(text="🕐 Свое время", callback_data="reminder_time_custom")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ]
        ]
    )
    
    await message.answer(
        "⏰ <b>Создание напоминания</b>\n\n"
        f"📝 <b>Текст:</b> {message.text}\n\n"
        "Выберите время напоминания:",
        reply_markup=time_keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("reminder_time_"))
async def quick_reminder_time_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора времени напоминания"""
    time_option = cb.data.replace("reminder_time_", "")
    
    data = await state.get_data()
    text = data.get("text")
    
    if not text:
        await cb.message.edit_text("❌ Ошибка: текст напоминания не найден.")
        await state.clear()
        return
    
    # Если выбрано свое время, переходим к вводу
    if time_option == "custom":
        await state.set_state(QuickReminderStates.waiting_custom_time)
        await cb.message.edit_text(
            "🕐 <b>Ввод своего времени</b>\n\n"
            f"📝 <b>Текст:</b> {text}\n\n"
            "Введите время в одном из форматов:\n\n"
            "• <b>Через X часов</b> (например: через 2 часа)\n"
            "• <b>Через X минут</b> (например: через 30 минут)\n"
            "• <b>В HH:MM</b> (например: 15:30)\n"
            "• <b>Завтра в HH:MM</b> (например: завтра в 9:00)\n"
            "• <b>Через X дней</b> (например: через 3 дня)\n\n"
            "Или нажмите кнопку для возврата к выбору времени.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к выбору времени", callback_data="reminder_back_to_time")]
                ]
            ),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    try:
        from datetime import datetime, timedelta
        
        # Вычисляем время напоминания
        now = datetime.now()
        if time_option == "1h":
            reminder_time = now + timedelta(hours=1)
            time_display = "через 1 час"
        elif time_option == "3h":
            reminder_time = now + timedelta(hours=3)
            time_display = "через 3 часа"
        elif time_option == "6h":
            reminder_time = now + timedelta(hours=6)
            time_display = "через 6 часов"
        elif time_option == "12h":
            reminder_time = now + timedelta(hours=12)
            time_display = "через 12 часов"
        elif time_option == "tomorrow":
            reminder_time = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
            time_display = "завтра утром в 9:00"
        elif time_option == "week":
            reminder_time = now + timedelta(weeks=1)
            time_display = "через неделю"
        else:
            reminder_time = now + timedelta(hours=1)
            time_display = "через 1 час"
        
        # Здесь можно добавить логику для создания напоминания в базе данных
        # Пока что просто показываем подтверждение
        
        await cb.message.edit_text(
            "✅ <b>Напоминание создано!</b>\n\n"
            f"⏰ <b>Текст:</b> {text}\n"
            f"🕐 <b>Время:</b> {time_display}\n"
            f"📅 <b>Дата:</b> {reminder_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            "Напоминание будет отправлено в указанное время.",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        await cb.message.edit_text(f"❌ Ошибка при создании напоминания: {str(e)}")
    
    await state.clear()
    await cb.answer()


@router.callback_query(F.data == "reminder_back_to_time")
async def reminder_back_to_time_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Вернуться к выбору времени напоминания"""
    data = await state.get_data()
    text = data.get("text")
    
    if not text:
        await cb.message.edit_text("❌ Ошибка: текст напоминания не найден.")
        await state.clear()
        return
    
    # Показываем меню времени
    time_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏰ Через 1 час", callback_data="reminder_time_1h"),
                InlineKeyboardButton(text="⏰ Через 3 часа", callback_data="reminder_time_3h")
            ],
            [
                InlineKeyboardButton(text="⏰ Через 6 часов", callback_data="reminder_time_6h"),
                InlineKeyboardButton(text="⏰ Через 12 часов", callback_data="reminder_time_12h")
            ],
            [
                InlineKeyboardButton(text="⏰ Завтра утром", callback_data="reminder_time_tomorrow"),
                InlineKeyboardButton(text="⏰ Через неделю", callback_data="reminder_time_week")
            ],
            [
                InlineKeyboardButton(text="🕐 Свое время", callback_data="reminder_time_custom")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ]
        ]
    )
    
    await cb.message.edit_text(
        "⏰ <b>Создание напоминания</b>\n\n"
        f"📝 <b>Текст:</b> {text}\n\n"
        "Выберите время напоминания:",
        reply_markup=time_keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(QuickReminderStates.waiting_custom_time)
async def quick_reminder_custom_time_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка ввода собственного времени напоминания"""
    data = await state.get_data()
    text = data.get("text")
    
    if not text:
        await message.answer("❌ Ошибка: текст напоминания не найден.")
        await state.clear()
        return
    
    try:
        from datetime import datetime, timedelta
        import re
        
        user_input = message.text.strip().lower()
        now = datetime.now()
        reminder_time = None
        time_display = ""
        
        # Паттерны для распознавания времени
        patterns = [
            # Через X часов
            (r'через (\d+) час(?:а|ов)?', lambda m: now + timedelta(hours=int(m.group(1))), 
             lambda m: f"через {m.group(1)} час(а/ов)"),
            
            # Через X минут
            (r'через (\d+) минут(?:у|ы)?', lambda m: now + timedelta(minutes=int(m.group(1))), 
             lambda m: f"через {m.group(1)} минут(у/ы)"),
            
            # В HH:MM (сегодня)
            (r'в (\d{1,2}):(\d{2})', lambda m: now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0), 
             lambda m: f"в {m.group(1)}:{m.group(2)}"),
            
            # Завтра в HH:MM
            (r'завтра в (\d{1,2}):(\d{2})', lambda m: (now + timedelta(days=1)).replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0), 
             lambda m: f"завтра в {m.group(1)}:{m.group(2)}"),
            
            # Через X дней
            (r'через (\d+) дн(?:ень|я|ей)?', lambda m: now + timedelta(days=int(m.group(1))), 
             lambda m: f"через {m.group(1)} дн(ень/я/ей)"),
            
            # В X часов (сегодня)
            (r'в (\d{1,2}) час(?:а|ов)?', lambda m: now.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0), 
             lambda m: f"в {m.group(1)}:00"),
        ]
        
        # Проверяем каждый паттерн
        for pattern, time_func, display_func in patterns:
            match = re.match(pattern, user_input)
            if match:
                reminder_time = time_func(match)
                time_display = display_func(match)
                break
        
        # Если время уже прошло, добавляем день
        if reminder_time and reminder_time <= now:
            if "завтра" not in user_input:
                reminder_time += timedelta(days=1)
                time_display = time_display.replace("в ", "завтра в ")
        
        if not reminder_time:
            await message.answer(
                "❌ <b>Не удалось распознать время</b>\n\n"
                "Пожалуйста, используйте один из форматов:\n\n"
                "• <b>Через X часов</b> (например: через 2 часа)\n"
                "• <b>Через X минут</b> (например: через 30 минут)\n"
                "• <b>В HH:MM</b> (например: 15:30)\n"
                "• <b>Завтра в HH:MM</b> (например: завтра в 9:00)\n"
                "• <b>Через X дней</b> (например: через 3 дня)\n\n"
                "Попробуйте еще раз или вернитесь к выбору времени.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад к выбору времени", callback_data="reminder_back_to_time")]
                    ]
                ),
                parse_mode="HTML"
            )
            return
        
        # Здесь можно добавить логику для создания напоминания в базе данных
        # Пока что просто показываем подтверждение
        
        await message.answer(
            "✅ <b>Напоминание создано!</b>\n\n"
            f"⏰ <b>Текст:</b> {text}\n"
            f"🕐 <b>Время:</b> {time_display}\n"
            f"📅 <b>Дата:</b> {reminder_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            "Напоминание будет отправлено в указанное время.",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при создании напоминания:</b>\n{str(e)}\n\n"
            "Попробуйте использовать более простой формат времени.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к выбору времени", callback_data="reminder_back_to_time")]
                ]
            ),
            parse_mode="HTML"
        )
        return
    
    await state.clear()


@router.callback_query(F.data == "quick_add_todo")
async def quick_add_todo_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать быстрое добавление в To-Do"""
    await state.set_state(QuickTodoStates.waiting_title)
    await cb.message.edit_text(
        "📋 <b>Быстрое добавление в To-Do</b>\n\n"
        "Введите название задачи:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(QuickTodoStates.waiting_title)
async def quick_todo_title_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка названия задачи"""
    if len(message.text) > 200:
        await message.answer("❌ Название слишком длинное. Максимум 200 символов.")
        return
    
    await state.update_data(title=message.text)
    await state.set_state(QuickTodoStates.waiting_description)
    
    await message.answer(
        "📋 <b>Добавление задачи</b>\n\n"
        "Введите описание задачи (или '-' чтобы пропустить):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(QuickTodoStates.waiting_description)
async def quick_todo_description_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка описания задачи"""
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
                is_completed=False,
                is_daily=False
            )
            
            session.add(new_todo)
            await session.commit()
            
            await message.answer(
                "✅ <b>Задача добавлена!</b>\n\n"
                f"📋 <b>{title}</b>\n"
                f"📝 <b>Описание:</b> {desc or 'Не указано'}\n"
                f"📅 <b>Дата:</b> {date.today().strftime('%d.%m.%Y')}\n"
                f"🔴 <b>Приоритет:</b> Средний\n\n"
                "Задача добавлена в ваш список дел.",
                reply_markup=back_main_menu(),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении задачи: {str(e)}")
    
    await state.clear()
