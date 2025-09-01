from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.db.models import Book, BookStatus, BookQuote, BookThought, User
from app.db.session import session_scope
from app.keyboards.common import (
    books_menu, book_status_menu, book_add_status_menu, book_detail_keyboard, book_list_keyboard,
    book_edit_keyboard, book_rating_keyboard, book_ai_menu, back_main_menu
)
from app.services.llm import deepseek_complete

router = Router()


# FSM для добавления и редактирования книг
class BookFSM(StatesGroup):
    waiting_title = State()
    waiting_author = State()
    waiting_description = State()
    waiting_genre = State()
    waiting_total_pages = State()
    waiting_status = State()
    waiting_quote = State()
    waiting_thought = State()
    waiting_rating = State()
    waiting_ai_question = State()


# FSM для быстрого добавления цитат
class BookQuoteFSM(StatesGroup):
    waiting_quote = State()
    waiting_book_selection = State()
    waiting_page_number = State()


# FSM для редактирования
class BookEditFSM(StatesGroup):
    waiting_title = State()
    waiting_author = State()
    waiting_description = State()
    waiting_genre = State()
    waiting_total_pages = State()
    waiting_current_page = State()
    waiting_start_date = State()
    waiting_finish_date = State()
    waiting_notes = State()


@router.callback_query(F.data == "menu_books")
async def menu_books(cb: types.CallbackQuery) -> None:
    """Показать главное меню раздела книг"""
    await cb.message.edit_text(
        "📚 <b>Раздел книг</b>\n\n"
        "Здесь вы можете управлять своей библиотекой:\n"
        "• Добавлять книги для чтения\n"
        "• Отслеживать прогресс чтения\n"
        "• Сохранять цитаты и мысли\n"
        "• Получать советы от ИИ\n"
        "• Анализировать свои привычки чтения",
        reply_markup=books_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "books_add")
async def books_add_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать добавление новой книги"""
    await state.set_state(BookFSM.waiting_title)
    await cb.message.edit_text(
        "📚 <b>Добавление новой книги</b>\n\n"
        "Введите название книги:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )


@router.message(BookFSM.waiting_title)
async def books_add_title(message: types.Message, state: FSMContext) -> None:
    """Получить название книги"""
    data = await state.get_data()
    
    # Проверяем, не находимся ли мы в режиме поиска
    if data.get("search_mode"):
        # Это поиск, обрабатываем в другом обработчике
        return
    
    title = message.text.strip()
    if len(title) > 256:
        await message.answer("Название слишком длинное. Максимум 256 символов.")
        return
    
    await state.update_data(title=title)
    await state.set_state(BookFSM.waiting_author)
    await message.answer(
        "✍️ Введите автора книги (или отправьте '-' если автор неизвестен):",
        reply_markup=back_main_menu()
    )


@router.message(BookFSM.waiting_author)
async def books_add_author(message: types.Message, state: FSMContext) -> None:
    """Получить автора книги"""
    author = message.text.strip()
    if author == "-":
        author = None
    elif len(author) > 256:
        await message.answer("Имя автора слишком длинное. Максимум 256 символов.")
        return
    
    await state.update_data(author=author)
    await state.set_state(BookFSM.waiting_description)
    await message.answer(
        "📝 Введите краткое описание книги (или отправьте '-' если описание не нужно):",
        reply_markup=back_main_menu()
    )


@router.message(BookFSM.waiting_description)
async def books_add_description(message: types.Message, state: FSMContext) -> None:
    """Получить описание книги"""
    description = message.text.strip()
    if description == "-":
        description = None
    
    await state.update_data(description=description)
    await state.set_state(BookFSM.waiting_genre)
    await message.answer(
        "📚 Введите жанр книги (или отправьте '-' если жанр не указан):",
        reply_markup=back_main_menu()
    )


@router.message(BookFSM.waiting_genre)
async def books_add_genre(message: types.Message, state: FSMContext) -> None:
    """Получить жанр книги"""
    genre = message.text.strip()
    if genre == "-":
        genre = None
    elif len(genre) > 100:
        await message.answer("Название жанра слишком длинное. Максимум 100 символов.")
        return
    
    await state.update_data(genre=genre)
    await state.set_state(BookFSM.waiting_total_pages)
    await message.answer(
        "📄 Введите количество страниц в книге (или отправьте '-' если неизвестно):",
        reply_markup=back_main_menu()
    )


@router.message(BookFSM.waiting_total_pages)
async def books_add_pages(message: types.Message, state: FSMContext) -> None:
    """Получить количество страниц"""
    pages_text = message.text.strip()
    total_pages = None
    
    if pages_text != "-":
        try:
            total_pages = int(pages_text)
            if total_pages <= 0:
                await message.answer("Количество страниц должно быть положительным числом.")
                return
        except ValueError:
            await message.answer("Пожалуйста, введите число или '-'.")
            return
    
    await state.update_data(total_pages=total_pages)
    await state.set_state(BookFSM.waiting_status)
    
    # Показать меню выбора статуса
    await message.answer(
        "📖 Выберите статус книги:",
        reply_markup=book_add_status_menu()
    )


@router.callback_query(F.data.startswith("book_add_status_"))
async def books_add_status(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Получить статус книги при добавлении"""
    status_map = {
        "book_add_status_want_to_read": BookStatus.want_to_read,
        "book_add_status_reading": BookStatus.reading,
        "book_add_status_completed": BookStatus.completed,
        "book_add_status_abandoned": BookStatus.abandoned
    }
    
    status = status_map.get(cb.data)
    if not status:
        await cb.answer("Неизвестный статус")
        return
    
    data = await state.get_data()
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Создать книгу
        book = Book(
            user_id=db_user.id,
            title=data["title"],
            author=data["author"],
            description=data["description"],
            genre=data["genre"],
            total_pages=data["total_pages"],
            status=status
        )
        
        # Установить даты в зависимости от статуса
        if status == BookStatus.reading:
            book.start_date = date.today()
        elif status == BookStatus.completed:
            book.start_date = date.today()
            book.finish_date = date.today()
        
        session.add(book)
        await session.commit()
        
        # Получить ID созданной книги
        book_id = book.id
    
    await state.clear()
    
    # Показать подтверждение
    status_text = {
        BookStatus.want_to_read: "📚 добавлена в список для чтения",
        BookStatus.reading: "📖 отмечена как читаемая",
        BookStatus.completed: "✅ отмечена как прочитанная",
        BookStatus.abandoned: "❌ отмечена как брошенная"
    }[status]
    
    await cb.message.edit_text(
        f"📚 <b>Книга успешно добавлена!</b>\n\n"
        f"<b>Название:</b> {data['title']}\n"
        f"<b>Автор:</b> {data['author'] or 'Не указан'}\n"
        f"<b>Статус:</b> {status_text}\n\n"
        f"Теперь вы можете управлять этой книгой.",
        reply_markup=book_detail_keyboard(book_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "books_want_to_read")
async def books_want_to_read(cb: types.CallbackQuery) -> None:
    """Показать список книг для чтения"""
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        books = (await session.execute(
            select(Book).where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.want_to_read
            ).order_by(Book.created_at.desc())
        )).scalars().all()
    
    if not books:
        await cb.message.edit_text(
            "📚 <b>Список книг для чтения</b>\n\n"
            "У вас пока нет книг в этом разделе.\n"
            "Добавьте первую книгу!",
            reply_markup=books_menu(),
            parse_mode="HTML"
        )
    else:
        book_list = [(book.id, book.title, book.author) for book in books]
        await cb.message.edit_text(
            "📚 <b>Книги для чтения</b>\n\n"
            f"Найдено книг: {len(books)}",
            reply_markup=book_list_keyboard(book_list, "want_to_read"),
            parse_mode="HTML"
        )
    
    # Убираем await cb.answer() так как используем edit_text


@router.callback_query(F.data == "books_reading")
async def books_reading(cb: types.CallbackQuery) -> None:
    """Показать список читаемых книг"""
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        books = (await session.execute(
            select(Book).where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.reading
            ).order_by(Book.start_date.desc())
        )).scalars().all()
    
    if not books:
        await cb.message.edit_text(
            "📖 <b>Читаемые книги</b>\n\n"
            "У вас пока нет книг в этом разделе.\n"
            "Начните читать первую книгу!",
            reply_markup=books_menu(),
            parse_mode="HTML"
        )
    else:
        book_list = [(book.id, book.title, book.author) for book in books]
        await cb.message.edit_text(
            "📖 <b>Читаемые книги</b>\n\n"
            f"Найдено книг: {len(books)}",
            reply_markup=book_list_keyboard(book_list, "reading"),
            parse_mode="HTML"
        )
    
    # Убираем await cb.answer() так как используем edit_text


@router.callback_query(F.data == "books_completed")
async def books_completed(cb: types.CallbackQuery) -> None:
    """Показать список прочитанных книг"""
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        books = (await session.execute(
            select(Book).where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.completed
            ).order_by(Book.finish_date.desc())
        )).scalars().all()
    
    if not books:
        await cb.message.edit_text(
            "✅ <b>Прочитанные книги</b>\n\n"
            "У вас пока нет прочитанных книг.\n"
            "Завершите чтение первой книги!",
            reply_markup=books_menu(),
            parse_mode="HTML"
        )
    else:
        book_list = [(book.id, book.title, book.author) for book in books]
        await cb.message.edit_text(
            "✅ <b>Прочитанные книги</b>\n\n"
            f"Найдено книг: {len(books)}",
            reply_markup=book_list_keyboard(book_list, "completed"),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data.startswith("book_view:"))
async def book_view(cb: types.CallbackQuery) -> None:
    """Показать детальную информацию о книге"""
    book_id = int(cb.data.split(":")[1])
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        book = (await session.execute(
            select(Book)
            .options(joinedload(Book.quotes), joinedload(Book.thoughts))
            .where(Book.id == book_id, Book.user_id == db_user.id)
        )).unique().scalar_one_or_none()
        
        if not book:
            await cb.answer("Книга не найдена")
            return
        
        # Статистика
        quotes_count = len(book.quotes)
        thoughts_count = len(book.thoughts)
        
        # Прогресс чтения
        progress_text = ""
        if book.status == BookStatus.reading and book.current_page and book.total_pages:
            progress_percent = int((book.current_page / book.total_pages) * 100)
            progress_text = f"\n📖 <b>Прогресс:</b> {book.current_page}/{book.total_pages} ({progress_percent}%)"
        
        # Статус
        status_emoji = {
            BookStatus.want_to_read: "📚",
            BookStatus.reading: "📖",
            BookStatus.completed: "✅",
            BookStatus.abandoned: "❌"
        }[book.status]
        
        status_text = {
            BookStatus.want_to_read: "Хочу прочитать",
            BookStatus.reading: "Читаю сейчас",
            BookStatus.completed: "Прочитана",
            BookStatus.abandoned: "Бросил читать"
        }[book.status]
        
        # Рейтинг
        rating_text = ""
        if book.rating:
            rating_text = f"\n⭐ <b>Рейтинг:</b> {'⭐' * book.rating}"
        
        # Даты
        dates_text = ""
        if book.start_date:
            dates_text += f"\n📅 <b>Начал читать:</b> {book.start_date.strftime('%d.%m.%Y')}"
        if book.finish_date:
            dates_text += f"\n✅ <b>Завершил:</b> {book.finish_date.strftime('%d.%m.%Y')}"
        
        # Цитаты и мысли
        content_text = ""
        if quotes_count > 0:
            content_text += f"\n💬 <b>Цитат:</b> {quotes_count}"
        if thoughts_count > 0:
            content_text += f"\n💭 <b>Мыслей:</b> {thoughts_count}"
        
        await cb.message.edit_text(
            f"{status_emoji} <b>{book.title}</b>\n\n"
            f"<b>Автор:</b> {book.author or 'Не указан'}\n"
            f"<b>Статус:</b> {status_text}\n"
            f"<b>Жанр:</b> {book.genre or 'Не указан'}\n"
            f"<b>Страниц:</b> {book.total_pages or 'Не указано'}"
            f"{rating_text}"
            f"{dates_text}"
            f"{progress_text}"
            f"{content_text}\n\n"
            f"<b>Описание:</b>\n{book.description or 'Описание не добавлено'}",
            reply_markup=book_detail_keyboard(book_id),
            parse_mode="HTML"
        )
    
    # Убираем await cb.answer() так как используем edit_text


@router.callback_query(F.data.startswith("book_add_quote:"))
async def book_add_quote_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать добавление цитаты"""
    book_id = int(cb.data.split(":")[1])
    await state.set_state(BookFSM.waiting_quote)
    await state.update_data(book_id=book_id)
    
    await cb.message.edit_text(
        "💬 <b>Добавление цитаты</b>\n\n"
        "Введите текст цитаты:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(BookFSM.waiting_quote)
async def book_add_quote_text(message: types.Message, state: FSMContext) -> None:
    """Получить текст цитаты"""
    quote_text = message.text.strip()
    if not quote_text:
        await message.answer("Цитата не может быть пустой.")
        return
    
    data = await state.get_data()
    book_id = data["book_id"]
    
    async with session_scope() as session:
        quote = BookQuote(
            book_id=book_id,
            quote_text=quote_text
        )
        session.add(quote)
        await session.commit()
    
    await state.clear()
    
    await message.answer(
        "💬 <b>Цитата добавлена!</b>\n\n"
        f"«{quote_text}»\n\n"
        "Теперь вы можете добавить еще цитаты или вернуться к книге.",
        reply_markup=book_detail_keyboard(book_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("book_add_thought:"))
async def book_add_thought_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать добавление мысли"""
    book_id = int(cb.data.split(":")[1])
    await state.set_state(BookFSM.waiting_thought)
    await state.update_data(book_id=book_id)
    
    await cb.message.edit_text(
        "💭 <b>Добавление мысли</b>\n\n"
        "Введите вашу мысль или размышление о книге:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(BookFSM.waiting_thought)
async def book_add_thought_text(message: types.Message, state: FSMContext) -> None:
    """Получить текст мысли"""
    thought_text = message.text.strip()
    if not thought_text:
        await message.answer("Мысль не может быть пустой.")
        return
    
    data = await state.get_data()
    book_id = data["book_id"]
    
    async with session_scope() as session:
        thought = BookThought(
            book_id=book_id,
            thought_text=thought_text,
            thought_type="insight"
        )
        session.add(thought)
        await session.commit()
    
    await state.clear()
    
    await message.answer(
        "💭 <b>Мысль добавлена!</b>\n\n"
        f"«{thought_text}»\n\n"
        "Теперь вы можете добавить еще мысли или вернуться к книге.",
        reply_markup=book_detail_keyboard(book_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("book_ai_question:"))
async def book_ai_question_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать вопрос к ИИ о книге"""
    # Сразу отвечаем на callback query, чтобы избежать ошибки "query is too old"
    await cb.answer()
    
    book_id = int(cb.data.split(":")[1])
    await state.set_state(BookFSM.waiting_ai_question)
    await state.update_data(book_id=book_id)
    
    await cb.message.edit_text(
        "🤖 <b>Вопрос к ИИ о книге</b>\n\n"
        "Выберите тип вопроса или введите свой:",
        reply_markup=book_ai_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("book_ai_"))
async def book_ai_question_handle(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработать предустановленные вопросы к ИИ"""
    # Сразу отвечаем на callback query, чтобы избежать ошибки "query is too old"
    await cb.answer()
    
    question_type = cb.data.split("_")[1]
    data = await state.get_data()
    book_id = data["book_id"]
    
    # Получить информацию о книге
    async with session_scope() as session:
        book = (await session.execute(
            select(Book)
            .options(joinedload(Book.quotes), joinedload(Book.thoughts))
            .where(Book.id == book_id)
        )).unique().scalar_one()
    
    # Сформировать вопрос в зависимости от типа
    question_map = {
        "what_is": "Что это за книга? Расскажи кратко о содержании и авторе.",
        "main_ideas": "Какие основные идеи и концепции рассматриваются в этой книге?",
        "who_for": "Кому подойдет эта книга? Кто получит от нее наибольшую пользу?",
        "summary": "Дай краткое содержание этой книги в 3-4 абзаца.",
        "quotes_analysis": "Проанализируй цитаты из этой книги и объясни их значение.",
        "personal_advice": "Дай персональный совет по чтению этой книги."
    }
    
    question = question_map.get(question_type, "Расскажи об этой книге.")
    
    # Сформировать контекст для ИИ
    context = f"Книга: {book.title}"
    if book.author:
        context += f" (автор: {book.author})"
    if book.description:
        context += f"\nОписание: {book.description}"
    if book.genre:
        context += f"\nЖанр: {book.genre}"
    
    # Добавить цитаты и мысли если есть
    if book.quotes:
        quotes_text = "\nЦитаты:\n" + "\n".join([f"«{q.quote_text}»" for q in book.quotes[:3]])
        context += quotes_text
    
    if book.thoughts:
        thoughts_text = "\nМысли читателя:\n" + "\n".join([f"• {t.thought_text}" for t in book.thoughts[:3]])
        context += thoughts_text
    
    # Показать индикатор загрузки
    loading_message = await cb.message.edit_text(
        f"🤖 <b>Генерирую ответ ИИ...</b>\n\n"
        f"<b>Вопрос:</b> {question}\n\n"
        "⏳ Пожалуйста, подождите, ИИ анализирует книгу...\n"
        "📚 Анализирую информацию о книге\n"
        "💭 Обрабатываю цитаты и мысли\n"
        "🤖 Формирую ответ...",
        reply_markup=book_detail_keyboard(book_id),
        parse_mode="HTML"
    )
    
    # Небольшая пауза для лучшего UX
    import asyncio
    await asyncio.sleep(0.5)
    
    # Получить ответ от ИИ
    try:
        ai_response = await deepseek_complete(
            f"{question}\n\nКонтекст:\n{context}",
            system="Ты эксперт по литературе. Отвечай кратко, но информативно. Используй эмодзи для лучшего восприятия. Если нужно указать рейтинг или важность, используй эмодзи звезд ⭐ вместо символа *. Не используй HTML-разметку, только обычный текст с эмодзи."
        )
        
        # Очистить ответ ИИ от проблемных символов
        ai_response_clean = ai_response.replace('*', '⭐')  # Звездочки на эмодзи
        ai_response_clean = ai_response_clean.replace('<', '&lt;')  # Защита от HTML
        ai_response_clean = ai_response_clean.replace('>', '&gt;')  # Защита от HTML
        
        # Заменить сообщение загрузки на готовый ответ
        await loading_message.edit_text(
            f"🤖 <b>Ответ ИИ о книге</b>\n\n"
            f"<b>Вопрос:</b> {question}\n\n"
            f"<b>Ответ:</b>\n{ai_response_clean}",
            reply_markup=book_detail_keyboard(book_id),
            parse_mode="HTML"
        )
    except Exception as e:
        # Заменить сообщение загрузки на сообщение об ошибке
        await loading_message.edit_text(
            f"❌ <b>Ошибка при обращении к ИИ</b>\n\n"
            f"<b>Вопрос:</b> {question}\n\n"
            f"Не удалось получить ответ от ИИ.\n"
            f"<b>Причина:</b> {str(e)}\n\n"
            "🔄 Попробуйте еще раз или обратитесь к администратору.",
            reply_markup=book_detail_keyboard(book_id),
            parse_mode="HTML"
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("book_view_quotes:"))
async def book_view_quotes(cb: types.CallbackQuery) -> None:
    """Показать все цитаты по книге"""
    book_id = int(cb.data.split(":")[1])
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        book = (await session.execute(
            select(Book).where(Book.id == book_id, Book.user_id == db_user.id)
        )).scalar_one_or_none()
        
        if not book:
            await cb.answer("Книга не найдена")
            return
        
        quotes = (await session.execute(
            select(BookQuote).where(BookQuote.book_id == book_id).order_by(BookQuote.created_at.desc())
        )).scalars().all()
    
    if not quotes:
        await cb.message.edit_text(
            f"📚 <b>Цитаты по книге «{book.title}»</b>\n\n"
            "У вас пока нет сохраненных цитат по этой книге.\n"
            "Добавьте первую цитату!",
            reply_markup=book_detail_keyboard(book_id),
            parse_mode="HTML"
        )
        return
    
    # Создаем клавиатуру для навигации по цитатам
    quotes_text = f"📚 <b>Цитаты по книге «{book.title}»</b>\n\n"
    quotes_text += f"Всего цитат: {len(quotes)}\n\n"
    
    for i, quote in enumerate(quotes, 1):
        quotes_text += f"<b>{i}.</b> «{quote.quote_text}»\n"
        if quote.page_number:
            quotes_text += f"   📄 Страница: {quote.page_number}\n"
        if quote.context:
            quotes_text += f"   💭 Контекст: {quote.context}\n"
        quotes_text += f"   📅 {quote.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    # Добавляем кнопку "Назад к книге"
    back_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад к книге", callback_data=f"book_view:{book_id}")
            ]
        ]
    )
    
    await cb.message.edit_text(
        quotes_text,
        reply_markup=back_keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("book_view_thoughts:"))
async def book_view_thoughts(cb: types.CallbackQuery) -> None:
    """Показать все мысли по книге"""
    book_id = int(cb.data.split(":")[1])
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        book = (await session.execute(
            select(Book).where(Book.id == book_id, Book.user_id == db_user.id)
        )).scalar_one_or_none()
        
        if not book:
            await cb.answer("Книга не найдена")
            return
        
        thoughts = (await session.execute(
            select(BookThought).where(BookThought.book_id == book_id).order_by(BookThought.created_at.desc())
        )).scalars().all()
    
    if not thoughts:
        await cb.message.edit_text(
            f"💭 <b>Мысли по книге «{book.title}»</b>\n\n"
            "У вас пока нет сохраненных мыслей по этой книге.\n"
            "Добавьте первую мысль!",
            reply_markup=book_detail_keyboard(book_id),
            parse_mode="HTML"
        )
        return
    
    # Создаем клавиатуру для навигации по мыслям
    thoughts_text = f"💭 <b>Мысли по книге «{book.title}»</b>\n\n"
    thoughts_text += f"Всего мыслей: {len(thoughts)}\n\n"
    
    for i, thought in enumerate(thoughts, 1):
        thoughts_text += f"<b>{i}.</b> {thought.thought_text}\n"
        thoughts_text += f"   🏷️ Тип: {thought.thought_type}\n"
        thoughts_text += f"   📅 {thought.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    # Добавляем кнопку "Назад к книге"
    back_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад к книге", callback_data=f"book_view:{book_id}")
            ]
        ]
    )
    
    await cb.message.edit_text(
        thoughts_text,
        reply_markup=back_keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "books_stats")
async def books_stats(cb: types.CallbackQuery) -> None:
    """Показать статистику чтения"""
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Общая статистика
        total_books = (await session.execute(
            select(func.count(Book.id)).where(Book.user_id == db_user.id)
        )).scalar()
        
        want_to_read = (await session.execute(
            select(func.count(Book.id)).where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.want_to_read
            )
        )).scalar()
        
        reading = (await session.execute(
            select(func.count(Book.id)).where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.reading
            )
        )).scalar()
        
        completed = (await session.execute(
            select(func.count(Book.id)).where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.completed
            )
        )).scalar()
        
        abandoned = (await session.execute(
            select(func.count(Book.id)).where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.abandoned
            )
        )).scalar()
        
        # Статистика по цитатам и мыслям
        total_quotes = (await session.execute(
            select(func.count(BookQuote.id))
            .join(Book)
            .where(Book.user_id == db_user.id)
        )).scalar()
        
        total_thoughts = (await session.execute(
            select(func.count(BookThought.id))
            .join(Book)
            .where(Book.user_id == db_user.id)
        )).scalar()
        
        # Средний рейтинг прочитанных книг
        avg_rating = (await session.execute(
            select(func.avg(Book.rating))
            .where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.completed,
                Book.rating.isnot(None)
            )
        )).scalar()
        
        avg_rating_text = f"{avg_rating:.1f}⭐" if avg_rating else "Нет оценок"
        
        # Книги с лучшим рейтингом
        top_books = (await session.execute(
            select(Book.title, Book.rating)
            .where(
                Book.user_id == db_user.id,
                Book.status == BookStatus.completed,
                Book.rating.isnot(None)
            )
            .order_by(Book.rating.desc())
            .limit(3)
        )).all()
        
        top_books_text = ""
        if top_books:
            top_books_text = "\n\n<b>Топ-3 книги:</b>\n"
            for i, (title, rating) in enumerate(top_books, 1):
                top_books_text += f"{i}. {title} - {'⭐' * rating}\n"
    
    await cb.message.edit_text(
        "📊 <b>Статистика чтения</b>\n\n"
        f"📚 <b>Всего книг:</b> {total_books}\n"
        f"📖 <b>Хочу прочитать:</b> {want_to_read}\n"
        f"📖 <b>Читаю сейчас:</b> {reading}\n"
        f"✅ <b>Прочитано:</b> {completed}\n"
        f"❌ <b>Брошено:</b> {abandoned}\n\n"
        f"💬 <b>Всего цитат:</b> {total_quotes}\n"
        f"💭 <b>Всего мыслей:</b> {total_thoughts}\n"
        f"⭐ <b>Средний рейтинг:</b> {avg_rating_text}"
        f"{top_books_text}",
        reply_markup=books_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


# ==================== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ====================

@router.callback_query(F.data.startswith("book_edit:"))
async def book_edit_start(cb: types.CallbackQuery) -> None:
    """Начать редактирование книги"""
    book_id = int(cb.data.split(":")[1])
    await cb.message.edit_text(
        "✏️ <b>Редактирование книги</b>\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=book_edit_keyboard(book_id),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("book_delete_confirm:"))
async def book_delete_confirm(cb: types.CallbackQuery) -> None:
    """Подтверждение удаления книги"""
    book_id = int(cb.data.split(":")[1])
    
    # Создаем клавиатуру подтверждения
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ Да, удалить", callback_data=f"book_delete:{book_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"book_view:{book_id}")
            ]
        ]
    )
    
    await cb.message.edit_text(
        "⚠️ <b>Подтверждение удаления</b>\n\n"
        "Вы уверены, что хотите удалить эту книгу?\n"
        "Все цитаты и мысли также будут удалены.\n\n"
        "Это действие нельзя отменить!",
        reply_markup=confirm_keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("book_delete:"))
async def book_delete(cb: types.CallbackQuery) -> None:
    """Удалить книгу"""
    book_id = int(cb.data.split(":")[1])
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        book = (await session.execute(
            select(Book).where(Book.id == book_id, Book.user_id == db_user.id)
        )).scalar_one_or_none()
        
        if not book:
            await cb.answer("Книга не найдена")
            return
        
        book_title = book.title
        session.delete(book)
        await session.commit()
    
    await cb.message.edit_text(
        f"🗑️ <b>Книга удалена</b>\n\n"
        f"Книга «{book_title}» была успешно удалена из вашей библиотеки.",
        reply_markup=books_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("book_change_status:"))
async def book_change_status_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать изменение статуса книги"""
    book_id = int(cb.data.split(":")[1])
    await state.update_data(book_id=book_id)
    await cb.message.edit_text(
        "📖 <b>Изменение статуса книги</b>\n\n"
        "Выберите новый статус:",
        reply_markup=book_status_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("book_rate:"))
async def book_rate_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать оценку книги"""
    book_id = int(cb.data.split(":")[1])
    await state.update_data(book_id=book_id)
    await cb.message.edit_text(
        "⭐ <b>Оценка книги</b>\n\n"
        "Поставьте оценку от 1 до 5 звезд:",
        reply_markup=book_rating_keyboard(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("book_rate_"))
async def book_rate_handle(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработать оценку книги"""
    rating = int(cb.data.split("_")[2])
    user = cb.from_user
    
    # Получить book_id из состояния
    data = await state.get_data()
    book_id = data.get("book_id")
    
    if not book_id:
        await cb.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Не удалось определить книгу для оценки.",
            reply_markup=books_menu(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Применить оценку к книге
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        book = (await session.execute(
            select(Book).where(Book.id == book_id, Book.user_id == db_user.id)
        )).scalar_one_or_none()
        
        if not book:
            await cb.message.edit_text(
                "❌ <b>Ошибка</b>\n\n"
                "Книга не найдена.",
                reply_markup=books_menu(),
                parse_mode="HTML"
            )
            await cb.answer()
            return
        
        # Обновить рейтинг
        book.rating = rating
        await session.commit()
    
    await state.clear()
    
    await cb.message.edit_text(
        f"⭐ <b>Оценка {rating} звезд применена!</b>\n\n"
        f"Книга «{book.title}» получила оценку {'⭐' * rating}",
        reply_markup=book_detail_keyboard(book_id),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "book_rating_cancel")
async def book_rating_cancel(cb: types.CallbackQuery) -> None:
    """Отменить оценку книги"""
    await cb.message.edit_text(
        "❌ <b>Оценка отменена</b>\n\n"
        "Вы можете оценить книгу позже.",
        reply_markup=books_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "book_ai_back")
async def book_ai_back(cb: types.CallbackQuery) -> None:
    """Вернуться из меню ИИ"""
    await cb.message.edit_text(
        "📚 <b>Раздел книг</b>\n\n"
        "Здесь вы можете управлять своей библиотекой:\n"
        "• Добавлять книги для чтения\n"
        "• Отслеживать прогресс чтения\n"
        "• Сохранять цитаты и мысли\n"
        "• Получать советы от ИИ\n"
        "• Анализировать свои привычки чтения",
        reply_markup=books_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("book_status_"))
async def book_change_status_apply(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Применить изменение статуса книги"""
    status_map = {
        "book_status_want_to_read": BookStatus.want_to_read,
        "book_status_reading": BookStatus.reading,
        "book_status_completed": BookStatus.completed,
        "book_status_abandoned": BookStatus.abandoned
    }
    
    status = status_map.get(cb.data)
    if not status:
        await cb.answer("Неизвестный статус")
        return
    
    data = await state.get_data()
    book_id = data.get("book_id")
    
    if not book_id:
        await cb.message.edit_text(
            "❌ <b>Ошибка</b>\n\n"
            "Не удалось определить книгу для изменения статуса.",
            reply_markup=books_menu(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    user = cb.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        book = (await session.execute(
            select(Book).where(Book.id == book_id, Book.user_id == db_user.id)
        )).scalar_one_or_none()
        
        if not book:
            await cb.message.edit_text(
                "❌ <b>Ошибка</b>\n\n"
                "Книга не найдена.",
                reply_markup=books_menu(),
                parse_mode="HTML"
            )
            await cb.answer()
            return
        
        # Обновить статус и даты
        old_status = book.status
        book.status = status
        
        # Установить даты в зависимости от нового статуса
        if status == BookStatus.reading and not book.start_date:
            book.start_date = date.today()
        elif status == BookStatus.completed:
            if not book.start_date:
                book.start_date = date.today()
            book.finish_date = date.today()
        
        await session.commit()
    
    await state.clear()
    
    # Показать подтверждение
    status_text = {
        BookStatus.want_to_read: "📚 Хочу прочитать",
        BookStatus.reading: "📖 Читаю сейчас",
        BookStatus.completed: "✅ Прочитана",
        BookStatus.abandoned: "❌ Бросил читать"
    }[status]
    
    await cb.message.edit_text(
        f"📖 <b>Статус книги изменен!</b>\n\n"
        f"Книга «{book.title}» теперь имеет статус: {status_text}",
        reply_markup=book_detail_keyboard(book_id),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "books_search")
async def books_search_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начать поиск книг"""
    await state.set_state(BookFSM.waiting_title)
    await state.update_data(search_mode=True)
    
    await cb.message.edit_text(
        "🔍 <b>Поиск книг</b>\n\n"
        "Введите название или часть названия книги для поиска:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(BookFSM.waiting_title)
async def books_search_handle(message: types.Message, state: FSMContext) -> None:
    """Обработать поиск книг"""
    data = await state.get_data()
    if not data.get("search_mode"):
        return
    
    search_query = message.text.strip()
    if not search_query:
        await message.answer("Введите текст для поиска.")
        return
    
    user = message.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Поиск по названию и автору
        books = (await session.execute(
            select(Book).where(
                Book.user_id == db_user.id,
                Book.title.ilike(f"%{search_query}%")
            ).order_by(Book.title)
        )).scalars().all()
        
        # Поиск по автору
        author_books = (await session.execute(
            select(Book).where(
                Book.user_id == db_user.id,
                Book.author.ilike(f"%{search_query}%")
            ).order_by(Book.title)
        )).scalars().all()
        
        # Объединить результаты, убрав дубликаты
        all_books = list({book.id: book for book in books + author_books}.values())
    
    await state.clear()
    
    if not all_books:
        await message.answer(
            f"🔍 <b>Поиск: {search_query}</b>\n\n"
            "Книги не найдены. Попробуйте изменить запрос.",
            reply_markup=books_menu(),
            parse_mode="HTML"
        )
    else:
        book_list = [(book.id, book.title, book.author) for book in all_books]
        await message.answer(
            f"🔍 <b>Поиск: {search_query}</b>\n\n"
            f"Найдено книг: {len(all_books)}",
            reply_markup=book_list_keyboard(book_list),
            parse_mode="HTML"
        )


# ==================== ОБРАБОТЧИКИ БЫСТРОГО ДОБАВЛЕНИЯ ЦИТАТ ====================

@router.message(BookQuoteFSM.waiting_quote)
async def book_quote_text_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка текста цитаты для быстрого добавления"""
    if len(message.text) > 1000:
        await message.answer("❌ Цитата слишком длинная. Максимум 1000 символов.")
        return
    
    await state.update_data(quote_text=message.text)
    
    # Получаем список книг из состояния
    data = await state.get_data()
    books = data.get("available_books", [])
    
    if not books:
        await message.answer("❌ Ошибка: список книг не найден.")
        await state.clear()
        return
    
    # Создаем клавиатуру для выбора книги
    keyboard = []
    for book in books:
        author_text = f" - {book.author}" if book.author else ""
        status_icon = "📖" if book.status == BookStatus.reading else "✅"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{status_icon} {book.title}{author_text}",
                callback_data=f"quick_quote_book:{book.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_main")])
    
    await state.set_state(BookQuoteFSM.waiting_book_selection)
    await message.answer(
        "📚 <b>Выберите книгу для цитаты</b>\n\n"
        "К какой книге относится эта цитата?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("quick_quote_book:"))
async def book_quote_book_selection_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора книги для цитаты"""
    book_id = int(cb.data.split(":")[1])
    
    await state.update_data(selected_book_id=book_id)
    await state.set_state(BookQuoteFSM.waiting_page_number)
    
    await cb.message.edit_text(
        "📄 <b>Укажите номер страницы</b>\n\n"
        "Введите номер страницы, где находится цитата (или '-' чтобы пропустить):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(BookQuoteFSM.waiting_page_number)
async def book_quote_page_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка номера страницы для цитаты"""
    page_text = message.text.strip()
    page_number = None
    
    if page_text != "-":
        try:
            page_number = int(page_text)
            if page_number < 0:
                await message.answer("❌ Номер страницы должен быть положительным числом.")
                return
        except ValueError:
            await message.answer("❌ Введите корректный номер страницы или '-' чтобы пропустить.")
            return
    
    # Получаем данные из состояния
    data = await state.get_data()
    quote_text = data.get("quote_text")
    book_id = data.get("selected_book_id")
    
    if not quote_text or not book_id:
        await message.answer("❌ Ошибка: данные цитаты не найдены.")
        await state.clear()
        return
    
    # Сохраняем цитату в базу данных
    user = message.from_user
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Проверяем, что книга принадлежит пользователю
        book = await session.execute(
            select(Book).where(Book.id == book_id, Book.user_id == db_user.id)
        )
        book = book.scalar_one_or_none()
        
        if not book:
            await message.answer("❌ Ошибка: книга не найдена.")
            await state.clear()
            return
        
        # Создаем новую цитату
        new_quote = BookQuote(
            book_id=book_id,
            quote_text=quote_text,
            page_number=page_number
        )
        session.add(new_quote)
        await session.commit()
    
    await state.clear()
    
    # Формируем сообщение об успехе
    page_info = f" (стр. {page_number})" if page_number else ""
    author_text = f" - {book.author}" if book.author else ""
    
    await message.answer(
        f"✅ <b>Цитата успешно добавлена!</b>\n\n"
        f"📚 Книга: {book.title}{author_text}\n"
        f"📝 Цитата: {quote_text[:100]}{'...' if len(quote_text) > 100 else ''}{page_info}\n\n"
        f"Цитата сохранена в разделе книг.",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
