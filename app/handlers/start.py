from __future__ import annotations

from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User, Book, BookStatus
from app.keyboards.common import main_menu, start_keyboard, back_main_menu
from app.db.models.motivation import Motivation

router = Router()


PILLARS = [
    "Ответственность",
    "Концепт отложенных перемен",
    "Наличие цели",
    "Осознание главного навыка как мужчины",
    "Система - ключ к достижению цели",
    "Создание характера победителя",
    "Главная определенная цель",
]


@router.message(CommandStart())
async def start_handler(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        existing = await session.execute(select(User).where(User.telegram_id == user.id))
        instance = existing.scalar_one_or_none()
        if not instance:
            instance = User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            session.add(instance)

    main_goal = None
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        if mot and mot.main_year_goal:
            main_goal = mot.main_year_goal
    header = "Добро пожаловать на Гладиаторскую арену жизни!\nЗдесь ты собираешь характер победителя через систему ежедневных практик.\n\n"
    if main_goal:
        header += f"🎯 Главная цель года: {main_goal}\n\n"
    header += "Выбери раздел:"
    await message.answer(header, reply_markup=main_menu())
    
    # Отправляем дополнительное сообщение с reply клавиатурой
    from app.keyboards.common import main_reply_keyboard
    await message.answer(
        "🚀 Используйте кнопки ниже для быстрых действий:",
        reply_markup=main_reply_keyboard()
    )


@router.message(Command("pillars"))
async def pillars_handler(message: types.Message) -> None:
    await message.answer("7 опор:\n- " + "\n- ".join(PILLARS))


@router.message(Command("motivation"))
async def motivation_handler(message: types.Message) -> None:
    from app.services.reminders import LAWS_OF_ARENA
    import random

    principle = random.choice(LAWS_OF_ARENA)
    await message.answer(f"Мотивация дня:\n\n{principle}")


@router.message(Command("hide_keyboard"))
async def hide_keyboard_handler(message: types.Message) -> None:
    """Скрыть reply клавиатуру"""
    from app.keyboards.common import hide_keyboard
    await message.answer("⌨️ Клавиатура скрыта", reply_markup=hide_keyboard())


@router.message(lambda message: message.text == "🚀 Старт")
async def start_button_handler(message: types.Message) -> None:
    """Обработчик кнопки Старт в reply клавиатуре"""
    user = message.from_user
    if not user:
        return
    
    main_goal = None
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        if mot and mot.main_year_goal:
            main_goal = mot.main_year_goal
    
    header = "🚀 **Добро пожаловать обратно на Гладиаторскую арену жизни!**\n\n"
    if main_goal:
        header += f"🎯 **Главная цель года:** {main_goal}\n\n"
    header += "Выбери раздел для работы:"
    
    await message.answer(header, reply_markup=main_menu(), parse_mode="Markdown")


# Обработчики для кнопок быстрых действий в reply клавиатуре
@router.message(F.text == "📝 Записать цитату")
async def quick_quote_button_handler(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки Записать цитату"""
    from app.handlers.books import BookQuoteFSM
    
    # Проверяем, есть ли у пользователя книги
    user = message.from_user
    if not user:
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Получаем книги пользователя (читает сейчас или прочитал)
        books = await session.execute(
            select(Book).where(
                Book.user_id == db_user.id,
                Book.status.in_([BookStatus.reading, BookStatus.completed])
            ).order_by(Book.title)
        )
        books_list = books.scalars().all()
    
    if not books_list:
        await message.answer(
            "📚 <b>Нет книг для добавления цитат</b>\n\n"
            "У вас нет книг со статусом 'Читаю сейчас' или 'Прочитана'.\n"
            "Сначала добавьте книгу в разделе 📚 Книги.",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        return
    
    # Сохраняем список книг в состоянии
    await state.update_data(available_books=books_list)
    
    # Устанавливаем состояние и отправляем сообщение
    await state.set_state(BookQuoteFSM.waiting_quote)
    await message.answer(
        "📝 <b>Быстрое добавление цитаты</b>\n\n"
        "Введите текст цитаты:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(F.text == "📚 Записать мысль")
async def quick_thought_button_handler(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки Записать мысль"""
    from app.handlers.quick_actions import QuickThoughtStates
    
    # Устанавливаем состояние и отправляем сообщение
    await state.set_state(QuickThoughtStates.waiting_thought)
    await message.answer(
        "📚 <b>Быстрое добавление мысли</b>\n\n"
        "Введите вашу мысль:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(F.text == "📋 Добавить в To-Do")
async def quick_todo_button_handler(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки Добавить в To-Do"""
    from app.handlers.todo import TodoStates
    
    # Устанавливаем состояние и отправляем сообщение
    await state.set_state(TodoStates.waiting_title)
    await message.answer(
        "📝 <b>Добавление новой задачи</b>\n\n"
        "Введите название задачи:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(F.text == "💰 Добавить расход")
async def quick_expense_button_handler(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки Добавить расход"""
    from app.handlers.quick_actions import QuickExpenseStates
    
    # Устанавливаем состояние и отправляем сообщение
    await state.set_state(QuickExpenseStates.waiting_amount)
    await message.answer(
        "💰 <b>Быстрое добавление расхода</b>\n\n"
        "Введите сумму расхода:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(F.text == "🎯 Добавить цель")
async def quick_goal_button_handler(message: types.Message, state: FSMContext) -> None:
    """Обработчик кнопки Добавить цель"""
    from app.handlers.goals import GoalFSM
    
    # Устанавливаем состояние и отправляем сообщение
    await state.set_state(GoalFSM.waiting_title)
    await message.answer(
        "🎯 <b>Создание новой цели</b>\n\n"
        "Введите название вашей цели.\n\n"
        "Примеры:\n"
        "• Пробежать 10 км за 45 минут\n"
        "• Прочитать 12 книг в этом году\n"
        "• Накопить 500,000 рублей на отпуск\n"
        "• Выучить английский до уровня B2",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(F.text == "💭 Просмотр мыслей")
async def view_thoughts_button_handler(message: types.Message) -> None:
    """Обработчик кнопки Просмотр мыслей из reply клавиатуры"""
    from app.handlers.quick_actions import view_thoughts_handler
    
    # Создаем mock callback query для вызова существующего обработчика
    class MockCallbackQuery:
        def __init__(self, message, from_user):
            self.message = message
            self.from_user = from_user
            self.data = "view_thoughts"
        
        async def answer(self):
            pass
    
    mock_cb = MockCallbackQuery(message, message.from_user)
    await view_thoughts_handler(mock_cb)


@router.message(F.text == "✨ Один идеальный день")
async def perfect_day_button_handler(message: types.Message) -> None:
    """Обработчик кнопки Один идеальный день"""
    from app.handlers.daily_reminders import perfect_day_menu
    
    # Создаем mock callback query для вызова существующего обработчика
    class MockCallbackQuery:
        def __init__(self, message, from_user):
            self.message = message
            self.from_user = from_user
            self.data = "perfect_day_plan"
        
        async def answer(self):
            pass
    
    mock_cb = MockCallbackQuery(message, message.from_user)
    await perfect_day_menu(mock_cb)


@router.message(F.text == "🏠 Главное меню")
async def main_menu_button_handler(message: types.Message) -> None:
    """Обработчик кнопки Главное меню"""
    user = message.from_user
    if not user:
        return
    
    main_goal = None
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        mot = (
            await session.execute(select(Motivation).where(Motivation.user_id == db_user.id))
        ).scalar_one_or_none()
        if mot and mot.main_year_goal:
            main_goal = mot.main_year_goal
    
    header = "🏠 <b>Главное меню</b>\n\n"
    if main_goal:
        header += f"🎯 <b>Главная цель года:</b> {main_goal}\n\n"
    header += "Выбери раздел для работы:"
    
    await message.answer(header, reply_markup=main_menu(), parse_mode="HTML")


