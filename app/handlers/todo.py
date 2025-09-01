from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from aiogram.filters import Command

from app.db.models import Todo, User
from app.db.session import session_scope
from app.keyboards.common import (
    todo_menu, todo_priority_menu, todo_edit_menu, 
    todo_list_keyboard, todo_view_keyboard, todo_daily_reminder_keyboard,
    todo_type_menu, back_main_menu
)
from app.services.todo_reminders import send_test_todo_reminder

router = Router()


class TodoStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_date = State()
    waiting_priority = State()
    waiting_reminder = State()
    edit_title = State()
    edit_description = State()
    edit_date = State()
    edit_priority = State()
    edit_reminder = State()


@router.callback_query(F.data == "menu_todo")
async def todo_main_menu(cb: types.CallbackQuery) -> None:
    """Главное меню To-Do раздела"""
    await cb.message.edit_text(
        "📝 <b>To-Do раздел</b>\n\n"
        "Управляйте своими задачами и ежедневными делами.",
        reply_markup=todo_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_add")
async def todo_add_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начало добавления новой задачи - выбор типа"""
    await cb.message.edit_text(
        "📝 <b>Добавление новой задачи</b>\n\n"
        "Выберите тип задачи:",
        reply_markup=todo_type_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_type_single")
async def todo_type_single_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Выбор разовой задачи"""
    await state.update_data(is_daily=False)
    await state.set_state(TodoStates.waiting_title)
    await cb.message.edit_text(
        "📝 <b>Добавление разовой задачи</b>\n\n"
        "Введите название задачи:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_type_daily")
async def todo_type_daily_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Выбор ежедневной задачи"""
    await state.update_data(is_daily=True)
    await state.set_state(TodoStates.waiting_title)
    await cb.message.edit_text(
        "🔄 <b>Добавление ежедневной задачи</b>\n\n"
        "Введите название задачи:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(TodoStates.waiting_title)
async def todo_title_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка названия задачи"""
    if len(message.text) > 500:
        await message.answer("❌ Название слишком длинное. Максимум 500 символов.")
        return
    
    await state.update_data(title=message.text)
    
    # Проверяем, является ли задача ежедневной
    data = await state.get_data()
    if data.get("is_daily", False):
        # Для ежедневных задач пропускаем описание и дату, сразу к приоритету
        await state.set_state(TodoStates.waiting_priority)
        await message.answer(
            "🔴 Выберите приоритет задачи:",
            reply_markup=todo_priority_menu()
        )
    else:
        # Для разовых задач продолжаем обычный процесс
        await state.set_state(TodoStates.waiting_description)
        await message.answer(
            "📝 Введите описание задачи (или отправьте '-' чтобы пропустить):",
            reply_markup=back_main_menu()
        )


@router.message(TodoStates.waiting_description)
async def todo_description_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка описания задачи"""
    description = message.text if message.text != "-" else None
    await state.update_data(description=description)
    await state.set_state(TodoStates.waiting_date)
    await message.answer(
        "📅 Введите дату выполнения в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ\n"
        "Или отправьте 'сегодня', 'завтра', 'через неделю':",
        reply_markup=back_main_menu()
    )


@router.message(TodoStates.waiting_date)
async def todo_date_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка даты задачи"""
    date_text = message.text.lower().strip()
    
    # Парсим специальные даты
    if date_text == "сегодня":
        due_date = date.today()
    elif date_text == "завтра":
        due_date = date.today() + timedelta(days=1)
    elif date_text == "через неделю":
        due_date = date.today() + timedelta(days=7)
    else:
        try:
            # Пробуем сначала полный формат (4 цифры года)
            due_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        except ValueError:
            try:
                # Пробуем короткий формат (2 цифры года)
                due_date = datetime.strptime(date_text, "%d.%m.%y").date()
            except ValueError:
                await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ или ДД.ММ.ГГ", reply_markup=back_main_menu())
                return
    
    await state.update_data(due_date=due_date)
    await state.set_state(TodoStates.waiting_priority)
    await message.answer(
        "🔴 Выберите приоритет задачи:",
        reply_markup=todo_priority_menu()
    )


@router.callback_query(F.data.startswith("todo_priority_"))
async def todo_priority_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора приоритета"""
    priority = cb.data.replace("todo_priority_", "")
    
    if priority not in ["high", "medium", "low"]:
        await cb.answer("❌ Неверный приоритет")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    
    # Проверяем, редактируем ли мы существующую задачу или создаем новую
    todo_id = data.get("todo_id")
    
    if todo_id:
        # Редактируем существующую задачу
        async with session_scope() as session:
            user = await session.execute(
                select(User).where(User.telegram_id == cb.from_user.id)
            )
            db_user = user.scalar_one()
            
            todo = await session.execute(
                select(Todo).where(
                    and_(
                        Todo.id == todo_id,
                        Todo.user_id == db_user.id
                    )
                )
            )
            todo_obj = todo.scalar_one()
            
            # Обновляем приоритет
            todo_obj.priority = priority
            await session.commit()
            
            await cb.answer("✅ Приоритет задачи обновлен!")
            
            # Показываем обновленную задачу
            await cb.message.edit_text(
                f"📝 <b>Задача обновлена:</b>\n\n"
                f"<b>Название:</b> {todo_obj.title}\n"
                f"<b>Описание:</b> {(todo_obj.description or 'Не указано').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')}\n"
                f"<b>Дата:</b> {todo_obj.due_date.strftime('%d.%m.%Y')}\n"
                f"<b>Приоритет:</b> {priority}\n"
                f"<b>Ежедневная:</b> {'Да' if todo_obj.is_daily else 'Нет'}",
                reply_markup=todo_edit_menu(todo_id),
                parse_mode="HTML"
            )
    else:
        # Создаем новую задачу
        await state.update_data(priority=priority)
        
        # Переходим к выбору времени напоминания
        await state.set_state(TodoStates.waiting_reminder)
        await cb.message.edit_text(
            "⏰ <b>Настройка напоминаний</b>\n\n"
            "Хотите ли вы получать напоминания о задаче?\n\n"
            "• <b>Да</b> - получать напоминания в указанное время\n"
            "• <b>Нет</b> - без напоминаний\n\n"
            "Выберите вариант:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Да", callback_data="todo_reminder_yes")],
                [types.InlineKeyboardButton(text="❌ Нет", callback_data="todo_reminder_no")],
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_todo")]
            ]),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "todo_reminder_yes")
async def todo_reminder_yes_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Пользователь выбрал получать напоминания"""
    await state.update_data(wants_reminder=True)
    await cb.message.edit_text(
        "⏰ <b>Время напоминания</b>\n\n"
        "Введите время для напоминания в формате ЧЧ:ММ\n\n"
        "Примеры:\n"
        "• 09:00 - утром\n"
        "• 18:00 - вечером\n"
        "• 21:00 - перед сном\n\n"
        "Или отправьте 'нет' чтобы пропустить:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_reminder_no")
async def todo_reminder_no_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Пользователь выбрал не получать напоминания"""
    await state.update_data(wants_reminder=False, reminder_time=None)
    await create_todo_from_state(cb, state)


@router.message(TodoStates.waiting_reminder)
async def todo_reminder_time_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка времени напоминания"""
    if message.text.lower() == "нет":
        await state.update_data(wants_reminder=False, reminder_time=None)
    else:
        # Проверяем формат времени
        try:
            time_str = message.text.strip()
            if ":" not in time_str:
                await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 09:00)", reply_markup=back_main_menu())
                return
            
            hour, minute = map(int, time_str.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time")
            
            await state.update_data(wants_reminder=True, reminder_time=time_str)
        except ValueError:
            await message.answer("❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 09:00)", reply_markup=back_main_menu())
            return
    
    # Создаем задачу
    await create_todo_from_state(message, state)


async def create_todo_from_state(message_or_cb, state: FSMContext) -> None:
    """Создает задачу из данных состояния"""
    data = await state.get_data()
    
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == message_or_cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Для ежедневных задач используем сегодняшнюю дату, для разовых - указанную пользователем
        due_date = date.today() if data.get("is_daily", False) else data["due_date"]
        description = data.get("description") if not data.get("is_daily", False) else None
        
        # Настройки напоминания
        reminder_time = data.get("reminder_time") if data.get("wants_reminder", False) else None
        is_reminder_active = bool(reminder_time)
        
        todo = Todo(
            user_id=db_user.id,
            title=data["title"],
            description=description,
            due_date=due_date,
            priority=data["priority"],
            is_daily=data.get("is_daily", False),
            reminder_time=reminder_time,
            is_reminder_active=is_reminder_active
        )
        session.add(todo)
        await session.commit()
    
    # Формируем сообщение о созданной задаче
    priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    priority_text = {"high": "Высокий", "medium": "Средний", "low": "Низкий"}
    task_type = "🔄 Ежедневная" if data.get("is_daily", False) else "📅 Разовая"
    
    # Формируем сообщение в зависимости от типа задачи
    if data.get("is_daily", False):
        message_text = (
            f"✅ <b>Ежедневная задача создана!</b>\n\n"
            f"📝 <b>Название:</b> {data['title']}\n"
            f"🔴 <b>Приоритет:</b> {priority_icons[data['priority']]} {priority_text[data['priority']]}\n"
            f"🔄 <b>Тип:</b> {task_type}\n"
            f"📅 <b>Показывается каждый день</b>"
        )
        
        if data.get("wants_reminder") and data.get("reminder_time"):
            message_text += f"\n⏰ <b>Напоминания:</b> каждый день в {data['reminder_time']}"
        else:
            message_text += "\n⏰ <b>Напоминания:</b> отключены"
    else:
        message_text = (
            f"✅ <b>Разовая задача создана!</b>\n\n"
            f"📝 <b>Название:</b> {data['title']}\n"
            f"📄 <b>Описание:</b> {data.get('description') or 'Не указано'}\n"
            f"📅 <b>Дата:</b> {data['due_date'].strftime('%d.%m.%Y')}\n"
            f"🔴 <b>Приоритет:</b> {priority_icons[data['priority']]} {priority_text[data['priority']]}\n"
            f"📅 <b>Тип:</b> {task_type}"
        )
        
        if data.get("wants_reminder") and data.get("reminder_time"):
            message_text += f"\n⏰ <b>Напоминания:</b> {data['due_date'].strftime('%d.%m.%Y')} в {data['reminder_time']}"
        else:
            message_text += "\n⏰ <b>Напоминания:</b> отключены"
    
    # Отправляем сообщение
    if hasattr(message_or_cb, 'message'):
        # Это callback query
        await message_or_cb.message.edit_text(
            message_text,
            reply_markup=todo_menu(),
            parse_mode="HTML"
        )
    else:
        # Это message
        await message_or_cb.answer(
            message_text,
            reply_markup=todo_menu(),
            parse_mode="HTML"
        )
    
    await state.clear()


@router.callback_query(F.data == "todo_list")
async def todo_list_handler(cb: types.CallbackQuery) -> None:
    """Показать список задач пользователя"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем все НЕ выполненные задачи пользователя
        todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == db_user.id,
                    Todo.is_completed == False
                )
            ).order_by(Todo.due_date, Todo.priority)
        )
        todos_list = todos.scalars().all()
    
    if not todos_list:
        await cb.message.edit_text(
            "📝 <b>Список задач</b>\n\n"
            "У вас пока нет задач. Создайте первую!",
            reply_markup=todo_menu(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Формируем список задач
    message_text = "📝 <b>Ваши задачи:</b>\n\n"
    
    current_date = None
    for todo in todos_list:
        if todo.due_date != current_date:
            current_date = todo.due_date
            date_str = "Сегодня" if todo.due_date == date.today() else \
                      "Завтра" if todo.due_date == date.today() + timedelta(days=1) else \
                      todo.due_date.strftime("%d.%m.%Y")
            message_text += f"\n📅 <b>{date_str}:</b>\n"
        
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        status_icon = "✅" if todo.is_completed else "⭕"
        # Экранируем HTML-символы в названии задачи
        safe_title = todo.title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        
        # Добавляем информацию о напоминаниях
        reminder_info = ""
        if todo.is_reminder_active and todo.reminder_time:
            reminder_info = f" ⏰{todo.reminder_time}"
        
        message_text += f"{status_icon} {priority_icons[todo.priority]} {safe_title}{reminder_info}\n"
    
    # Создаем клавиатуру для списка
    todos_data = [(todo.id, todo.title, todo.is_completed) for todo in todos_list]
    keyboard = todo_list_keyboard(todos_data)
    
    await cb.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_completed")
async def todo_completed_handler(cb: types.CallbackQuery) -> None:
    """Показать список выполненных задач пользователя"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем все выполненные задачи пользователя
        completed_todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == db_user.id,
                    Todo.is_completed == True
                )
            ).order_by(Todo.due_date.desc(), Todo.priority)
        )
        completed_list = completed_todos.scalars().all()
    
    if not completed_list:
        await cb.message.edit_text(
            "✅ <b>Выполненные задачи</b>\n\n"
            "У вас пока нет выполненных задач.",
            reply_markup=todo_menu(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Формируем список выполненных задач
    message_text = "✅ <b>Ваши выполненные задачи:</b>\n\n"
    
    current_date = None
    for todo in completed_list:
        if todo.due_date != current_date:
            current_date = todo.due_date
            date_str = "Сегодня" if todo.due_date == date.today() else \
                      "Вчера" if todo.due_date == date.today() - timedelta(days=1) else \
                      todo.due_date.strftime("%d.%m.%Y")
            message_text += f"\n📅 <b>{date_str}:</b>\n"
        
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        # Экранируем HTML-символы в названии задачи
        safe_title = todo.title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        
        # Добавляем информацию о напоминаниях
        reminder_info = ""
        if todo.is_reminder_active and todo.reminder_time:
            reminder_info = f" ⏰{todo.reminder_time}"
        
        message_text += f"✅ {priority_icons[todo.priority]} {safe_title}{reminder_info}\n"
    
    # Создаем клавиатуру для списка выполненных задач
    completed_data = [(todo.id, todo.title, True) for todo in completed_list]
    keyboard = todo_list_keyboard(completed_data)
    
    await cb.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("todo_view:"))
async def todo_view_handler(cb: types.CallbackQuery) -> None:
    """Показать детали задачи"""
    todo_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        todo = await session.execute(
            select(Todo).where(Todo.id == todo_id)
        )
        todo_obj = todo.scalar_one_or_none()
        
        if not todo_obj:
            await cb.answer("❌ Задача не найдена")
            return
        
        # Проверяем, что задача принадлежит пользователю
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        if todo_obj.user_id != db_user.id:
            await cb.answer("❌ Доступ запрещен")
            return
        
        # Формируем сообщение о задаче
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        priority_text = {"high": "Высокий", "medium": "Средний", "low": "Низкий"}
        status_text = "✅ Выполнено" if todo_obj.is_completed else "⭕ В процессе"
        daily_text = "🔄 Ежедневная" if todo_obj.is_daily else "📅 Разовая"
        
        message_text = (
            f"📝 <b>Задача #{todo_obj.id}</b>\n\n"
            f"📋 <b>Название:</b> {todo_obj.title}\n"
            f"📅 <b>Дата:</b> {todo_obj.due_date.strftime('%d.%m.%Y')}\n"
            f"🔴 <b>Приоритет:</b> {priority_icons[todo_obj.priority]} {priority_text[todo_obj.priority]}\n"
            f"📊 <b>Статус:</b> {status_text}\n"
            f"🔄 <b>Тип:</b> {daily_text}\n"
            f"⏰ <b>Создано:</b> {todo_obj.created_at.strftime('%d.%m.%Y %H:%M')}"
        )
        
        # Добавляем информацию о напоминаниях
        if todo_obj.is_reminder_active and todo_obj.reminder_time:
            if todo_obj.is_daily:
                message_text += f"\n🔔 <b>Напоминания:</b> каждый день в {todo_obj.reminder_time}"
            else:
                message_text += f"\n🔔 <b>Напоминания:</b> {todo_obj.due_date.strftime('%d.%m.%Y')} в {todo_obj.reminder_time}"
        else:
            message_text += "\n🔔 <b>Напоминания:</b> отключены"
        
        if todo_obj.description:
            # Экранируем HTML-символы в описании
            safe_description = todo_obj.description.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            message_text += f"\n\n📄 <b>Описание:</b>\n{safe_description}"
    
    await cb.message.edit_text(
        message_text,
        reply_markup=todo_view_keyboard(todo_id),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("todo_mark_complete:"))
async def todo_mark_complete_handler(cb: types.CallbackQuery) -> None:
    """Отметить задачу как выполненную"""
    todo_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        todo = await session.execute(
            select(Todo).where(Todo.id == todo_id)
        )
        todo_obj = todo.scalar_one_or_none()
        
        if not todo_obj:
            await cb.answer("❌ Задача не найдена")
            return
        
        # Проверяем, что задача принадлежит пользователю
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        if todo_obj.user_id != db_user.id:
            await cb.answer("❌ Доступ запрещен")
            return
        
        # Переключаем статус
        todo_obj.is_completed = not todo_obj.is_completed
        await session.commit()
        
        status_text = "✅ выполнена" if todo_obj.is_completed else "⭕ в процессе"
        await cb.answer(f"Задача {status_text}")
        
        # Если задача выполнена, предлагаем удалить её
        if todo_obj.is_completed:
            await cb.message.edit_text(
                f"✅ <b>Задача выполнена!</b>\n\n"
                f"📝 <b>{todo_obj.title}</b>\n\n"
                "Хотите удалить выполненную задачу из списка?",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(text="🗑️ Да, удалить", callback_data=f"todo_delete:{todo_id}"),
                            types.InlineKeyboardButton(text="📋 Оставить", callback_data=f"todo_view:{todo_id}")
                        ]
                    ]
                ),
                parse_mode="HTML"
            )
            return
    
    # Обновляем сообщение
    await todo_view_handler(cb)


@router.callback_query(F.data.startswith("todo_delete_confirm:"))
async def todo_delete_confirm_handler(cb: types.CallbackQuery) -> None:
    """Подтверждение удаления задачи"""
    todo_id = int(cb.data.split(":")[1])
    
    await cb.message.edit_text(
        f"🗑️ <b>Удаление задачи #{todo_id}</b>\n\n"
        "Вы уверены, что хотите удалить эту задачу?",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"todo_delete:{todo_id}"),
                    types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"todo_view:{todo_id}")
                ]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("todo_delete:"))
async def todo_delete_handler(cb: types.CallbackQuery) -> None:
    """Удаление задачи"""
    todo_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        todo = await session.execute(
            select(Todo).where(Todo.id == todo_id)
        )
        todo_obj = todo.scalar_one_or_none()
        
        if not todo_obj:
            await cb.answer("❌ Задача не найдена")
            return
        
        # Проверяем, что задача принадлежит пользователю
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        if todo_obj.user_id != db_user.id:
            await cb.answer("❌ Доступ запрещен")
            return
        
        # Удаляем задачу
        await session.delete(todo_obj)
        await session.commit()
        
        await cb.answer("✅ Задача удалена")
    
    # Возвращаемся к списку задач
    await todo_list_handler(cb)





@router.callback_query(F.data == "todo_edit")
async def todo_edit_start(cb: types.CallbackQuery) -> None:
    """Начало редактирования задачи"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем все задачи пользователя для выбора
        todos = await session.execute(
            select(Todo).where(Todo.user_id == db_user.id).order_by(Todo.due_date)
        )
        todos_list = todos.scalars().all()
    
    if not todos_list:
        await cb.message.edit_text(
            "✏️ <b>Редактирование задач</b>\n\n"
            "У вас пока нет задач для редактирования.",
            reply_markup=todo_menu(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Формируем список задач для выбора
    message_text = "✏️ <b>Выберите задачу для редактирования:</b>\n\n"
    
    for todo in todos_list:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        status_icon = "✅" if todo.is_completed else "⭕"
        message_text += f"{status_icon} {priority_icons[todo.priority]} {todo.title}\n"
    
    # Создаем клавиатуру для выбора задачи
    todos_data = [(todo.id, todo.title, todo.is_completed) for todo in todos_list]
    keyboard = todo_list_keyboard(todos_data)
    
    await cb.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_delete")
async def todo_delete_start(cb: types.CallbackQuery) -> None:
    """Начало удаления задачи"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем все задачи пользователя для выбора
        todos = await session.execute(
            select(Todo).where(Todo.user_id == db_user.id).order_by(Todo.due_date)
        )
        todos_list = todos.scalars().all()
    
    if not todos_list:
        await cb.message.edit_text(
            "🗑️ <b>Удаление задач</b>\n\n"
            "У вас пока нет задач для удаления.",
            reply_markup=todo_menu(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Формируем список задач для выбора
    message_text = "🗑️ <b>Выберите задачу для удаления:</b>\n\n"
    
    for todo in todos_list:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        status_icon = "✅" if todo.is_completed else "⭕"
        message_text += f"{status_icon} {priority_icons[todo.priority]} {todo.title}\n"
    
    # Создаем клавиатуру для выбора задачи
    todos_data = [(todo.id, todo.title, todo.is_completed) for todo in todos_list]
    keyboard = todo_list_keyboard(todos_data)
    
    await cb.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_complete")
async def todo_complete_start(cb: types.CallbackQuery) -> None:
    """Начало отметки задачи как выполненной"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем все невыполненные задачи пользователя
        todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == db_user.id,
                    Todo.is_completed == False
                )
            ).order_by(Todo.due_date)
        )
        todos_list = todos.scalars().all()
    
    if not todos_list:
        await cb.message.edit_text(
            "✅ <b>Отметка выполненных задач</b>\n\n"
            "У вас нет невыполненных задач.",
            reply_markup=todo_menu(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Формируем список задач для выбора
    message_text = "✅ <b>Выберите задачу для отметки как выполненной:</b>\n\n"
    
    for todo in todos_list:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        message_text += f"⭕ {priority_icons[todo.priority]} {todo.title}\n"
    
    # Создаем клавиатуру для выбора задачи
    todos_data = [(todo.id, todo.title, todo.is_completed) for todo in todos_list]
    keyboard = todo_list_keyboard(todos_data)
    
    await cb.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_daily")
async def todo_daily_handler(cb: types.CallbackQuery) -> None:
    """Показать ежедневные задачи"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем обычные ежедневные задачи (не на основе целей)
        regular_todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == db_user.id,
                    Todo.is_daily == True,
                    Todo.description.notlike("Ежедневная задача для достижения цели:%")
                )
            ).order_by(Todo.priority)
        )
        regular_list = regular_todos.scalars().all()
        
        # Получаем задачи на основе целей
        goal_based_todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == db_user.id,
                    Todo.is_daily == True,
                    Todo.description.like("Ежедневная задача для достижения цели:%")
                )
            ).order_by(Todo.priority)
        )
        goal_based_list = goal_based_todos.scalars().all()
        
        # Получаем сводки
        from app.services.daily_tasks_manager import get_separate_daily_tasks_summary
        summary = await get_separate_daily_tasks_summary(session, db_user.id)
    
    if not regular_list and not goal_based_list:
        await cb.message.edit_text(
            "🔄 <b>Ежедневные задачи</b>\n\n"
            "У вас пока нет ежедневных задач.\n\n"
            "💡 Создайте обычные ежедневные задачи или цели, и система автоматически будет создавать задачи для их достижения!",
            reply_markup=todo_menu(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Формируем сообщение с отдельными секциями
    message_text = "🔄 <b>Ваши ежедневные задачи:</b>\n\n"
    
    # Секция обычных задач
    if regular_list:
        message_text += "📋 <b>Обычные задачи:</b>\n"
        for todo in regular_list:
            priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            status_icon = "✅" if todo.is_completed else "⭕"
            message_text += f"{status_icon} {priority_icons[todo.priority]} {todo.title}\n"
        message_text += "\n"
    
    # Секция задач на основе целей
    if goal_based_list:
        message_text += "🎯 <b>Задачи на основе целей:</b>\n"
        for todo in goal_based_list:
            priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            status_icon = "✅" if todo.is_completed else "⭕"
            goal_title = todo.description.replace("Ежедневная задача для достижения цели: ", "") if todo.description else ""
            message_text += f"{status_icon} {priority_icons[todo.priority]} {todo.title}\n"
            message_text += f"   📎 Цель: {goal_title}\n"
        message_text += "\n"
    
    # Добавляем статистику
    message_text += f"📊 <b>Статистика:</b>\n"
    message_text += f"• Обычные задачи: {summary['regular']['total']} (выполнено: {summary['regular']['completed']})\n"
    message_text += f"• Задачи на основе целей: {summary['goal_based']['total']} (выполнено: {summary['goal_based']['completed']})\n"
    message_text += f"• Общий прогресс: {summary['overall']['completion_rate']:.1f}%"
    
    # Создаем клавиатуру
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎯 Задачи на основе целей", callback_data="todo_goal_based")],
        [types.InlineKeyboardButton(text="📋 Все задачи", callback_data="todo_list")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_todo")]
    ])
    
    await cb.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


# Обработчики для вечернего напоминания
@router.callback_query(F.data == "todo_add_tomorrow")
async def todo_add_tomorrow_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Добавить задачу на завтра из вечернего напоминания"""
    await cb.message.edit_text(
        "📝 <b>Добавление задачи на завтра</b>\n\n"
        "Выберите тип задачи:",
        reply_markup=todo_type_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_view_tomorrow")
async def todo_view_tomorrow_handler(cb: types.CallbackQuery) -> None:
    """Посмотреть задачи на завтра"""
    tomorrow = date.today() + timedelta(days=1)
    
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем задачи на завтра
        tomorrow_todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == db_user.id,
                    Todo.due_date == tomorrow
                )
            ).order_by(Todo.priority)
        )
        tomorrow_list = tomorrow_todos.scalars().all()
    
    if not tomorrow_list:
        await cb.message.edit_text(
            f"📅 <b>Задачи на {tomorrow.strftime('%d.%m.%Y')}</b>\n\n"
            "У вас пока нет задач на завтра.",
            reply_markup=todo_daily_reminder_keyboard(),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Формируем список задач на завтра
    message_text = f"📅 <b>Задачи на {tomorrow.strftime('%d.%m.%Y')}:</b>\n\n"
    
    for todo in tomorrow_list:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        status_icon = "✅" if todo.is_completed else "⭕"
        message_text += f"{status_icon} {priority_icons[todo.priority]} {todo.title}\n"
    
    await cb.message.edit_text(
        message_text,
        reply_markup=todo_daily_reminder_keyboard(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_copy_today")
async def todo_copy_today_handler(cb: types.CallbackQuery) -> None:
    """Скопировать сегодняшние задачи на завтра"""
    today = date.today()
    tomorrow = date.today() + timedelta(days=1)
    
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем сегодняшние задачи
        today_todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == db_user.id,
                    Todo.due_date == today
                )
            )
        )
        today_list = today_todos.scalars().all()
    
    if not today_list:
        await cb.answer("❌ У вас нет задач на сегодня")
        return
    
    # Копируем задачи на завтра
    copied_count = 0
    for todo in today_list:
        new_todo = Todo(
            user_id=db_user.id,
            title=todo.title,
            description=todo.description,
            due_date=tomorrow,
            priority=todo.priority,
            is_daily=todo.is_daily
        )
        session.add(new_todo)
        copied_count += 1
    
    await session.commit()
    
    await cb.answer(f"✅ Скопировано {copied_count} задач на завтра")
    
    # Показываем обновленный список задач на завтра
    await todo_view_tomorrow_handler(cb)


@router.callback_query(F.data == "todo_remind_later")
async def todo_remind_later_handler(cb: types.CallbackQuery) -> None:
    """Напомнить позже о составлении To-Do"""
    await cb.message.edit_text(
        "⏰ <b>Напоминание отложено</b>\n\n"
        "Я напомню вам о составлении To-Do списка через час.",
        reply_markup=todo_daily_reminder_keyboard(),
        parse_mode="HTML"
    )
    await cb.answer()
    
    # TODO: Добавить логику для отложенного напоминания через час


@router.callback_query(F.data == "todo_menu")
async def todo_menu_handler(cb: types.CallbackQuery) -> None:
    """Возврат в главное меню To-Do раздела"""
    await cb.message.edit_text(
        "📝 <b>To-Do раздел</b>\n\n"
        "Управляйте своими задачами и ежедневными делами.",
        reply_markup=todo_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_priority_high")
async def todo_priority_high_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Установка высокого приоритета для задачи"""
    await state.update_data(priority="high")
    await todo_priority_handler(cb, state)


@router.callback_query(F.data == "todo_priority_medium")
async def todo_priority_medium_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Установка среднего приоритета для задачи"""
    await state.update_data(priority="medium")
    await todo_priority_handler(cb, state)


@router.callback_query(F.data == "todo_priority_low")
async def todo_priority_low_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Установка низкого приоритета для задачи"""
    await state.update_data(priority="low")
    await todo_priority_handler(cb, state)


@router.callback_query(F.data.startswith("todo_edit_title:"))
async def todo_edit_title_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начало редактирования названия задачи"""
    todo_id = int(cb.data.split(":")[1])
    await state.set_state(TodoStates.edit_title)
    await state.update_data(todo_id=todo_id)
    await cb.message.edit_text(
        "✏️ <b>Редактирование названия</b>\n\n"
        "Введите новое название задачи:",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("todo_edit_description:"))
async def todo_edit_description_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начало редактирования описания задачи"""
    todo_id = int(cb.data.split(":")[1])
    await state.set_state(TodoStates.edit_description)
    await state.update_data(todo_id=todo_id)
    await cb.message.edit_text(
        "📝 <b>Редактирование описания</b>\n\n"
        "Введите новое описание задачи (или '-' чтобы убрать):",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("todo_edit_date:"))
async def todo_edit_date_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начало редактирования даты задачи"""
    todo_id = int(cb.data.split(":")[1])
    await state.set_state(TodoStates.edit_date)
    await state.update_data(todo_id=todo_id)
    await cb.message.edit_text(
        "📅 <b>Редактирование даты</b>\n\n"
        "Введите новую дату в формате ДД.ММ.ГГГГ или ДД.ММ.ГГ\n"
        "Или отправьте 'сегодня', 'завтра', 'через неделю':",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("todo_edit_priority:"))
async def todo_edit_priority_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начало редактирования приоритета задачи"""
    todo_id = int(cb.data.split(":")[1])
    await state.update_data(todo_id=todo_id)
    
    # Показываем меню выбора приоритета
    await cb.message.edit_text(
        "🔴 <b>Выберите новый приоритет</b>",
        reply_markup=todo_priority_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("todo_toggle_daily:"))
async def todo_toggle_daily_handler(cb: types.CallbackQuery) -> None:
    """Переключение ежедневного статуса задачи"""
    todo_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        todo = await session.execute(
            select(Todo).where(
                and_(
                    Todo.id == todo_id,
                    Todo.user_id == db_user.id
                )
            )
        )
        todo_obj = todo.scalar_one()
        
        # Переключаем статус
        todo_obj.is_daily = not todo_obj.is_daily
        await session.commit()
        
        status = "ежедневной" if todo_obj.is_daily else "обычной"
        await cb.answer(f"✅ Задача сделана {status}")
        
        # Возвращаемся в меню редактирования
        await cb.message.edit_text(
            "✏️ <b>Редактирование задачи</b>\n\n"
            f"<b>Название:</b> {todo_obj.title}\n"
            f"<b>Описание:</b> {(todo_obj.description or 'Не указано').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')}\n"
            f"<b>Дата:</b> {todo_obj.due_date.strftime('%d.%m.%Y')}\n"
            f"<b>Приоритет:</b> {todo_obj.priority}\n"
            f"<b>Ежедневная:</b> {'Да' if todo_obj.is_daily else 'Нет'}",
            reply_markup=todo_edit_menu(todo_id),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("todo_edit_menu:"))
async def todo_edit_menu_handler(cb: types.CallbackQuery) -> None:
    """Показать меню редактирования задачи"""
    todo_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        todo = await session.execute(
            select(Todo).where(
                and_(
                    Todo.id == todo_id,
                    Todo.user_id == db_user.id
                )
            )
        )
        todo_obj = todo.scalar_one()
        
        # Показываем информацию о задаче и меню редактирования
        await cb.message.edit_text(
            "✏️ <b>Редактирование задачи</b>\n\n"
            f"<b>Название:</b> {todo_obj.title}\n"
            f"<b>Описание:</b> {(todo_obj.description or 'Не указано').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')}\n"
            f"<b>Дата:</b> {todo_obj.due_date.strftime('%d.%m.%Y')}\n"
            f"<b>Приоритет:</b> {todo_obj.priority}\n"
            f"<b>Ежедневная:</b> {'Да' if todo_obj.is_daily else 'Нет'}",
            reply_markup=todo_edit_menu(todo_id),
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data == "todo_goal_based")
async def todo_goal_based_handler(cb: types.CallbackQuery) -> None:
    """Показать задачи на основе целей"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Получаем задачи на основе целей
        goal_based_todos = await session.execute(
            select(Todo).where(
                and_(
                    Todo.user_id == db_user.id,
                    Todo.is_daily == True,
                    Todo.description.like("Ежедневная задача для достижения цели:%")
                )
            ).order_by(Todo.priority)
        )
        goal_based_list = goal_based_todos.scalars().all()
        
        # Получаем сводку
        from app.services.daily_tasks_manager import get_goal_based_tasks_summary
        summary = await get_goal_based_tasks_summary(session, db_user.id)
    
    if not goal_based_list:
        await cb.message.edit_text(
            "🎯 <b>Задачи на основе целей</b>\n\n"
            "У вас пока нет задач на основе целей.\n\n"
            "💡 Создайте цели в разделе 'Цели', и система автоматически будет создавать ежедневные задачи для их достижения!",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🎯 Создать цель", callback_data="menu_goals")],
                [types.InlineKeyboardButton(text="🔄 Создать задачи из целей", callback_data="todo_create_from_goals")],
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_todo")]
            ]),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Формируем список задач на основе целей
    message_text = "🎯 <b>Задачи на основе целей:</b>\n\n"
    
    for todo in goal_based_list:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        status_icon = "✅" if todo.is_completed else "⭕"
        # Убираем префикс из описания для отображения и экранируем HTML
        goal_title = todo.description.replace("Ежедневная задача для достижения цели: ", "") if todo.description else ""
        safe_goal_title = goal_title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        message_text += f"{status_icon} {priority_icons[todo.priority]} {todo.title}\n"
        message_text += f"   📎 Цель: {safe_goal_title}\n\n"
    
    # Добавляем статистику
    message_text += f"📊 <b>Статистика:</b>\n"
    message_text += f"• Всего задач: {summary['total']}\n"
    message_text += f"• Выполнено: {summary['completed']}\n"
    message_text += f"• Осталось: {summary['pending']}\n"
    message_text += f"• Прогресс: {summary['completion_rate']:.1f}%"
    
    # Создаем клавиатуру
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 Создать новые задачи из целей", callback_data="todo_create_from_goals")],
        [types.InlineKeyboardButton(text="🗑️ Очистить старые выполненные", callback_data="todo_cleanup_goal_tasks")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_todo")]
    ])
    
    await cb.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_create_from_goals")
async def todo_create_from_goals_handler(cb: types.CallbackQuery) -> None:
    """Создать задачи на основе активных целей"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Создаем задачи на основе целей
        from app.services.daily_tasks_manager import create_goal_based_tasks
        created_tasks = await create_goal_based_tasks(session, db_user.id)
    
    if not created_tasks:
        await cb.message.edit_text(
            "🎯 <b>Создание задач из целей</b>\n\n"
            "У вас нет активных целей для создания задач.\n\n"
            "💡 Создайте цели в разделе 'Цели', и система автоматически будет создавать ежедневные задачи для их достижения!",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🎯 Создать цель", callback_data="menu_goals")],
                [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="todo_goal_based")]
            ]),
            parse_mode="HTML"
        )
        await cb.answer()
        return
    
    # Показываем созданные задачи
    message_text = f"✅ <b>Создано {len(created_tasks)} задач на основе целей:</b>\n\n"
    
    for task in created_tasks:
        priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        goal_title = task.description.replace("Ежедневная задача для достижения цели: ", "") if task.description else ""
        safe_goal_title = goal_title.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        message_text += f"⭕ {priority_icons[task.priority]} {task.title}\n"
        message_text += f"   📎 Цель: {safe_goal_title}\n\n"
    
    message_text += "💡 Эти задачи будут появляться каждый день автоматически!"
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎯 Посмотреть все задачи на основе целей", callback_data="todo_goal_based")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_todo")]
    ])
    
    await cb.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "todo_cleanup_goal_tasks")
async def todo_cleanup_goal_tasks_handler(cb: types.CallbackQuery) -> None:
    """Очистить старые выполненные задачи на основе целей"""
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        db_user = user.scalar_one()
        
        # Очищаем старые задачи
        from app.services.daily_tasks_manager import cleanup_old_goal_tasks
        deleted_count = await cleanup_old_goal_tasks(session, db_user.id, days_to_keep=7)
    
    if deleted_count == 0:
        await cb.answer("🗑️ Нет старых выполненных задач для удаления")
        return
    
    await cb.answer(f"🗑️ Удалено {deleted_count} старых выполненных задач")
    
    # Возвращаемся к списку задач на основе целей
    await todo_goal_based_handler(cb)


# Обработчики для состояний редактирования
@router.message(TodoStates.edit_title)
async def todo_edit_title_message_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка нового названия задачи"""
    if len(message.text) > 500:
        await message.answer("❌ Название слишком длинное. Максимум 500 символов.")
        return
    
    data = await state.get_data()
    todo_id = data.get("todo_id")
    
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        db_user = user.scalar_one()
        
        todo = await session.execute(
            select(Todo).where(
                and_(
                    Todo.id == todo_id,
                    Todo.user_id == db_user.id
                )
            )
        )
        todo_obj = todo.scalar_one()
        
        # Обновляем название
        todo_obj.title = message.text
        await session.commit()
        
        await message.answer("✅ Название задачи обновлено!")
        
        # Показываем обновленную задачу
        await message.answer(
            f"📝 <b>Задача обновлена:</b>\n\n"
            f"<b>Название:</b> {todo_obj.title}\n"
            f"<b>Описание:</b> {(todo_obj.description or 'Не указано').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')}\n"
            f"<b>Дата:</b> {todo_obj.due_date.strftime('%d.%m.%Y')}\n"
            f"<b>Приоритет:</b> {todo_obj.priority}\n"
            f"<b>Ежедневная:</b> {'Да' if todo_obj.is_daily else 'Нет'}",
            reply_markup=todo_edit_menu(todo_id),
            parse_mode="HTML"
        )
    
    await state.clear()


@router.message(TodoStates.edit_description)
async def todo_edit_description_message_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка нового описания задачи"""
    description = message.text if message.text != "-" else None
    
    data = await state.get_data()
    todo_id = data.get("todo_id")
    
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        db_user = user.scalar_one()
        
        todo = await session.execute(
            select(Todo).where(
                and_(
                    Todo.id == todo_id,
                    Todo.user_id == db_user.id
                )
            )
        )
        todo_obj = todo.scalar_one()
        
        # Обновляем описание
        todo_obj.description = description
        await session.commit()
        
        await message.answer("✅ Описание задачи обновлено!")
        
        # Показываем обновленную задачу
        await message.answer(
            f"📝 <b>Задача обновлена:</b>\n\n"
            f"<b>Название:</b> {todo_obj.title}\n"
            f"<b>Описание:</b> {(todo_obj.description or 'Не указано').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')}\n"
            f"<b>Дата:</b> {todo_obj.due_date.strftime('%d.%m.%Y')}\n"
            f"<b>Приоритет:</b> {todo_obj.priority}\n"
            f"<b>Ежедневная:</b> {'Да' if todo_obj.is_daily else 'Нет'}",
            reply_markup=todo_edit_menu(todo_id),
            parse_mode="HTML"
        )
    
    await state.clear()


@router.message(TodoStates.edit_date)
async def todo_edit_date_message_handler(message: types.Message, state: FSMContext) -> None:
    """Обработка новой даты задачи"""
    date_text = message.text.lower().strip()
    
    # Парсим специальные даты
    if date_text == "сегодня":
        due_date = date.today()
    elif date_text == "завтра":
        due_date = date.today() + timedelta(days=1)
    elif date_text == "через неделю":
        due_date = date.today() + timedelta(days=7)
    else:
        try:
            # Пробуем сначала полный формат (4 цифры года)
            due_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        except ValueError:
            try:
                # Пробуем короткий формат (2 цифры года)
                due_date = datetime.strptime(date_text, "%d.%m.%y").date()
            except ValueError:
                await message.answer(
                    "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ или ДД.ММ.ГГ или 'сегодня', 'завтра', 'через неделю'"
                )
                return
    
    data = await state.get_data()
    todo_id = data.get("todo_id")
    
    async with session_scope() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        db_user = user.scalar_one()
        
        todo = await session.execute(
            select(Todo).where(
                and_(
                    Todo.id == todo_id,
                    Todo.user_id == db_user.id
                )
            )
        )
        todo_obj = todo.scalar_one()
        
        # Обновляем дату
        todo_obj.due_date = due_date
        await session.commit()
        
        await message.answer("✅ Дата задачи обновлена!")
        
        # Показываем обновленную задачу
        await message.answer(
            f"📝 <b>Задача обновлена:</b>\n\n"
            f"<b>Название:</b> {todo_obj.title}\n"
            f"<b>Описание:</b> {(todo_obj.description or 'Не указано').replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')}\n"
            f"<b>Дата:</b> {todo_obj.due_date.strftime('%d.%m.%Y')}\n"
            f"<b>Приоритет:</b> {todo_obj.priority}\n"
            f"<b>Ежедневная:</b> {'Да' if todo_obj.is_daily else 'Нет'}",
            reply_markup=todo_edit_menu(todo_id),
            parse_mode="HTML"
        )
    
    await state.clear()


@router.message(Command("test_todo_reminder"))
async def test_todo_reminder(message: types.Message) -> None:
    """Отправляет тестовое напоминание по to-do задаче для проверки."""
    user = message.from_user
    if not user:
        return
    
    try:
        await message.answer("🧪 Отправляю тестовое напоминание по задаче...")
        await send_test_todo_reminder(user.id, "Тестовая задача", message.bot)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки тестового напоминания: {str(e)}")


@router.message(Command("test_goal_tasks"))
async def test_goal_tasks(message: types.Message) -> None:
    """Тестирует создание задач на основе целей."""
    user = message.from_user
    if not user:
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Создаем задачи на основе целей
            from app.services.daily_tasks_manager import create_goal_based_tasks
            created_tasks = await create_goal_based_tasks(session, db_user.id)
        
        if created_tasks:
            await message.answer(
                f"✅ Создано {len(created_tasks)} задач на основе целей!\n\n"
                f"Проверьте раздел 'Ежедневные дела' или 'Задачи на основе целей' в меню To-Do."
            )
        else:
            await message.answer(
                "ℹ️ Нет активных целей для создания задач.\n\n"
                "Создайте цели в разделе 'Цели', и система автоматически будет создавать ежедневные задачи для их достижения!"
            )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка создания задач на основе целей: {str(e)}")


@router.message(Command("reset_goal_tasks"))
async def reset_goal_tasks(message: types.Message) -> None:
    """Сбрасывает и создает заново задачи на основе целей."""
    user = message.from_user
    if not user:
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Сбрасываем задачи на основе целей
            from app.services.daily_tasks_manager import GoalTasksManager
            await GoalTasksManager.reset_daily_goal_tasks(session, db_user.id)
            
            # Создаем новые задачи на основе активных целей
            created_tasks = await GoalTasksManager.create_daily_tasks_from_goals(session, db_user.id)
        
        await message.answer(
            f"🔄 Задачи на основе целей сброшены и созданы заново!\n\n"
            f"Создано {len(created_tasks)} новых задач.\n\n"
            f"Проверьте раздел 'Ежедневные дела' или 'Задачи на основе целей' в меню To-Do."
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка сброса задач на основе целей: {str(e)}")


@router.message(Command("test_nutrition_todos"))
async def test_nutrition_todos(message: types.Message) -> None:
    """Тестирует создание задач питания."""
    user = message.from_user
    if not user:
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Создаем задачи питания
            from app.services.nutrition_todo_manager import create_nutrition_todos_for_user
            await create_nutrition_todos_for_user(session, db_user.id)
        
        await message.answer(
            "✅ Задачи питания созданы!\n\n"
            "Проверьте ваш To-Do список - там должны появиться задачи для времени готовки и покупок.\n\n"
            "Задачи создаются автоматически каждый день в 6:00 по вашему времени."
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка создания задач питания: {str(e)}")
