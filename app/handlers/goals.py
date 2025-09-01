from __future__ import annotations

from datetime import date

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from app.db.models import Goal, GoalScope, GoalStatus, ABAnalysis, User
from app.db.models.goal import GoalReminder
from app.db.session import session_scope
from app.services.llm import deepseek_complete
from app.utils.timezone_utils import get_user_time_info
from app.keyboards.common import back_main_menu


router = Router()


# FSM для добавления и редактирования целей
class GoalFSM(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_due_date = State()
    waiting_reminder_time = State()


# Мотивирующие сообщения для напоминаний
MOTIVATION_MESSAGES = [
    "Сегодня великий день! Сегодня реализация цели: {goal_title} 🎯✨",
    "Время действовать! Сегодня ты достигаешь цели: {goal_title} 🚀💪",
    "Сегодня особенный день - день достижения цели: {goal_title} 🌟🎉",
    "Помни о своей цели: {goal_title}. Сегодня ты на шаг ближе к успеху! 🔥",
    "Сегодня день, когда ты воплощаешь в жизнь цель: {goal_title} ⭐💫",
    "Твоя цель: {goal_title} ждет реализации сегодня! Время показать, на что ты способен! 🎯🔥",
    "Сегодня великолепный день для достижения цели: {goal_title} ✨🌟",
    "Помни, ради чего ты начал! Сегодня реализация цели: {goal_title} 🎯💪",
    "Сегодня день твоей цели: {goal_title}. Время действовать! 🚀⭐",
    "Сегодня ты становишься ближе к своей мечте! Цель: {goal_title} 🌟🎯"
]


@router.message(Command("goal_add"))
async def add_goal(message: types.Message) -> None:
    """Add a simple daily goal from text after command."""
    user = message.from_user
    if not user:
        return
    text = (message.text or "").replace("/goal_add", "").strip()
    if not text:
        await message.answer("Использование: /goal_add Ваша цель")
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        goal = Goal(
            user_id=db_user.id,
            scope=GoalScope.day,
            title=text,
            description=None,
            start_date=date.today(),
            status=GoalStatus.active,
        )
        session.add(goal)
            # AI: автогенерация SMART-описания
    status_msg = await message.answer("⏳ Генерирую SMART-описание...")
    smart_prompt = f"Оцени цель пользователя и оформи SMART-описание кратко: '{text}'. Выведи 5 пунктов: S,M,A,R,T."
    try:
        smart = await deepseek_complete(smart_prompt, system="Ты коуч по целям. Кратко и по делу.")

        await status_msg.edit_text("Цель добавлена ✅\nSMART:\n" + smart)
    except Exception:
        await status_msg.edit_text("Цель добавлена ✅")


@router.message(Command("goals"))
async def list_goals(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        goals = (await session.execute(select(Goal).where(Goal.user_id == db_user.id, Goal.status == GoalStatus.active))).scalars().all()
    if not goals:
        await message.answer("Активных целей нет")
        return
    lines = [f"[{g.scope}] {g.title}" for g in goals]
    await message.answer("Ваши цели:\n- " + "\n- ".join(lines))


@router.message(Command("ab"))
async def ab_analysis(message: types.Message) -> None:
    """Store quick A/B analysis: /ab сейчас | хочу."""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/ab", "", 1).strip()
    if "|" not in payload:
        await message.answer("Использование: /ab где_я_сейчас | где_хочу_быть")
        return
    current, desired = [p.strip() for p in payload.split("|", 1)]
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        session.add(ABAnalysis(user_id=db_user.id, current_state=current, desired_state=desired))
    # AI: краткий план действий
    status_msg = await message.answer("⏳ Генерирую план перехода A → B...")
    try:
        plan = await deepseek_complete(
            f"Сформируй краткий пошаговый план перехода из состояния A='{current}' в B='{desired}'. Дай 5 шагов.",
            system="Кратко, по делу, без воды.",
        )
        await status_msg.edit_text("A/B анализ сохранен ✅\nПлан:\n" + plan)
    except Exception:
        await status_msg.edit_text("A/B анализ сохранен ✅")


@router.message(Command("smart"))
async def smart_goal(message: types.Message) -> None:
    """Создать SMART-цель: /smart scope title | description | due_date(YYYY-MM-DD)"""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/smart", "", 1).strip()
    if payload.count("|") < 1:
        await message.answer("Пример: /smart 1m Пробежать 10км | Тренировки 3р/нед | 2025-10-01")
        return
    head, rest = payload.split(" ", 1)
    scope_map = {"5y": GoalScope.five_years, "1y": GoalScope.year, "1m": GoalScope.month, "1d": GoalScope.day}
    scope = scope_map.get(head, GoalScope.month)
    title, desc, *maybe_due = [p.strip() for p in rest.split("|")]
    due = date.fromisoformat(maybe_due[0]) if maybe_due else None
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        g = Goal(user_id=db_user.id, scope=scope, title=title, description=desc or None, start_date=date.today(), due_date=due)
        session.add(g)
    # AI: SMART-валидация
    status_msg = await message.answer("⏳ Анализирую SMART-критерии...")
    try:
        smart_feedback = await deepseek_complete(
            f"Проверь SMART цель: title='{title}', desc='{desc}', due='{due}'. Дай улучшения в 3-5 пунктах.",
            system="Эксперт SMART",
        )
        await status_msg.edit_text("SMART цель добавлена ✅\nРекомендации:\n" + smart_feedback)
    except Exception:
        await status_msg.edit_text("SMART цель добавлена ✅")


@router.callback_query(F.data == "goals_smart_hint")
async def goals_smart_hint(cb: types.CallbackQuery) -> None:
    """Показывает подсказку по SMART целям."""
    text = (
        "🎯 **SMART - методика постановки целей:**\n\n"
        "**S - Specific (Конкретная)**\n"
        "❌ Неправильно: 'Хочу быть здоровым'\n"
        "✅ Правильно: 'Пробежать 10 км за 45 минут'\n\n"
        "**M - Measurable (Измеримая)**\n"
        "❌ Неправильно: 'Больше читать'\n"
        "✅ Правильно: 'Читать 30 минут в день'\n\n"
        "**A - Achievable (Достижимая)**\n"
        "❌ Неправильно: 'Стать олимпийским чемпионом за месяц'\n"
        "✅ Правильно: 'Пробежать полумарафон через 6 месяцев'\n\n"
        "**R - Relevant (Релевантная)**\n"
        "❌ Неправильно: 'Выучить китайский' (если не планируете в Китай)\n"
        "✅ Правильно: 'Выучить английский для работы'\n\n"
        "**T - Time-bound (Ограниченная по времени)**\n"
        "❌ Неправильно: 'Когда-нибудь купить дом'\n"
        "✅ Правильно: 'Накопить на дом за 5 лет'\n\n"
        "**Примеры SMART целей:**\n"
        "• 🏃‍♂️ Пробежать 5 км за 25 минут к 1 июня 2025\n"
        "• 💰 Накопить 500,000 рублей на отпуск к декабрю 2025\n"
        "• 📚 Прочитать 12 книг по бизнесу в 2025 году\n"
        "• 🏋️‍♂️ Поднять жим лежа 100 кг к марту 2025\n\n"
        "**Команды для создания целей:**\n"
        "• `/goal_add Ваша цель` - простая цель на день\n"
        "• `/smart 1m Название | Описание | 2025-06-01` - SMART цель на месяц"
    )
    
    await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "goals_add")
async def goals_add_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начинает процесс добавления новой цели."""
    await state.set_state(GoalFSM.waiting_title)
    
    text = (
        "🎯 Создание новой цели:\n\n"
        "Введите название вашей цели.\n\n"
        "Примеры:\n"
        "• Пробежать 10 км за 45 минут\n"
        "• Прочитать 12 книг в этом году\n"
        "• Накопить 500,000 рублей на отпуск\n"
        "• Выучить английский до уровня B2"
    )
    
    await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode=None)
    await cb.answer()


@router.message(GoalFSM.waiting_title)
async def goals_add_title(message: types.Message, state: FSMContext) -> None:
    """Сохраняет название цели и запрашивает описание."""
    await state.update_data(title=message.text.strip())
    await state.set_state(GoalFSM.waiting_description)
    
    text = (
        "📝 Описание цели:\n\n"
        "Введите подробное описание вашей цели.\n\n"
        "Примеры описаний:\n"
        "• Тренироваться 3 раза в неделю, постепенно увеличивая дистанцию\n"
        "• Читать по 30 минут каждый день перед сном\n"
        "• Откладывать 20% от зарплаты каждый месяц\n"
        "• Заниматься с репетитором 2 раза в неделю"
    )
    
    await message.answer(text, reply_markup=back_main_menu(), parse_mode=None)


@router.message(GoalFSM.waiting_description)
async def goals_add_description(message: types.Message, state: FSMContext) -> None:
    """Сохраняет описание цели и запрашивает дату завершения."""
    await state.update_data(description=message.text.strip())
    await state.set_state(GoalFSM.waiting_due_date)
    
    text = (
        "📅 Дата завершения цели:\n\n"
        "Введите дату в формате ДД.ММ.ГГГГ\n\n"
        "Примеры:\n"
        "• 31.12.2025\n"
        "• 01.06.2025\n"
        "• 15.03.2025\n\n"
        "Или введите 'сегодня' для цели на сегодня"
    )
    
    await message.answer(text, reply_markup=back_main_menu(), parse_mode=None)





@router.message(GoalFSM.waiting_due_date)
async def goals_add_due_date(message: types.Message, state: FSMContext) -> None:
    """Сохраняет дату завершения цели, определяет scope и запрашивает время напоминания."""
    due_date_text = message.text.strip().lower()
    
    if due_date_text == "сегодня":
        due_date = date.today()
    else:
        try:
            # Парсим дату в формате ДД.ММ.ГГГГ
            if "." in due_date_text:
                day, month, year = due_date_text.split(".")
                due_date = date(int(year), int(month), int(day))
            else:
                # Пробуем ISO формат как fallback
                due_date = date.fromisoformat(due_date_text)
        except (ValueError, IndexError):
            await message.answer(
                "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ или 'сегодня'\n\n"
                "Попробуйте снова:",
                reply_markup=back_main_menu()
            )
            return
    
    # Определяем scope на основе разницы в днях
    today = date.today()
    days_diff = (due_date - today).days
    
    if days_diff <= 1:
        scope = GoalScope.day
    elif days_diff <= 7:
        scope = GoalScope.week
    elif days_diff <= 30:
        scope = GoalScope.month
    elif days_diff <= 90:
        scope = GoalScope.three_months
    elif days_diff <= 180:
        scope = GoalScope.six_months
    elif days_diff <= 365:
        scope = GoalScope.year
    else:
        scope = GoalScope.five_years
    
    await state.update_data(due_date=due_date, scope=scope)
    await state.set_state(GoalFSM.waiting_reminder_time)
    
    text = (
        "⏰ Время напоминания:\n\n"
        "Введите время для ежедневных напоминаний о цели в формате ЧЧ:ММ\n\n"
        "Примеры:\n"
        "• 09:00 - утром\n"
        "• 18:00 - вечером\n"
        "• 21:00 - перед сном\n\n"
        "Напоминания будут приходить каждый день в указанное время"
    )
    
    await message.answer(text, reply_markup=back_main_menu(), parse_mode=None)


@router.message(GoalFSM.waiting_reminder_time)
async def goals_add_reminder_time(message: types.Message, state: FSMContext) -> None:
    """Сохраняет время напоминания и создает цель."""
    reminder_time = message.text.strip().lower()
    
    if reminder_time == "нет":
        reminder_time = None
    
    # Получаем все данные из состояния
    data = await state.get_data()
    title = data.get("title")
    description = data.get("description")
    scope = data.get("scope")
    due_date = data.get("due_date")
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one()
        
        # Создаем цель
        goal = Goal(
            user_id=db_user.id,
            scope=scope,
            title=title,
            description=description,
            start_date=date.today(),
            due_date=due_date,
            status=GoalStatus.active
        )
        session.add(goal)
        await session.flush()  # Получаем ID цели
        
        # Если указано время напоминания, создаем напоминание
        if reminder_time:
            # Логируем локальное время пользователя
            time_info = get_user_time_info(db_user.timezone)
            print(f"🕐 Создание напоминания для цели '{title}' пользователем {db_user.telegram_id}")
            print(f"   📍 Часовой пояс: {time_info['timezone']}")
            print(f"   🕐 Локальное время пользователя: {time_info['user_local_time'].strftime('%H:%M:%S')}")
            print(f"   🌍 UTC время: {time_info['utc_time'].strftime('%H:%M:%S')}")
            print(f"   ⏰ Время напоминания: {reminder_time}")
            print(f"   📊 Смещение: {time_info['offset_hours']:+g} ч")
            
            reminder = GoalReminder(
                user_id=db_user.id,
                goal_id=goal.id,
                reminder_time=reminder_time,
                is_active=True
            )
            session.add(reminder)
        
        await session.commit()
    
    # Генерируем SMART-описание
    status_msg = await message.answer("⏳ Генерирую SMART-описание...")
    smart_prompt = f"Оцени цель пользователя и оформи SMART-описание: '{title}'. Выведи 5 пунктов с разметкой Markdown:\n\n**S (Конкретность):**\n**M (Измеримость):**\n**A (Достижимость):**\n**R (Релевантность):**\n**T (Ограниченность во времени):**"
    
    try:
        smart = await deepseek_complete(smart_prompt, system="Ты коуч по целям. Кратко и по делу.")
        

        
        await status_msg.edit_text(
            f"🎯 Цель создана успешно! ✅\n\n"
            f"**Название:** {title}\n"
            f"**Описание:** {description}\n"
            f"**Срок:** {due_date.strftime('%d.%m.%Y')}\n"
            f"**Напоминания:** {'Да' if reminder_time else 'Нет'}\n\n"
            f"**SMART-описание:**\n{smart}",
            parse_mode="Markdown"
        )
    except Exception:
        await status_msg.edit_text(
            f"🎯 Цель создана успешно! ✅\n\n"
            f"**Название:** {title}\n"
            f"**Описание:** {description}\n"
            f"**Срок:** {due_date.strftime('%d.%m.%Y')}\n"
            f"**Напоминания:** {'Да' if reminder_time else 'Нет'}\n\n"
            f"⚠️ Не удалось сгенерировать SMART-описание",
            parse_mode="Markdown"
        )
    
    await state.clear()


@router.callback_query(F.data == "goals_edit")
async def goals_edit_start(cb: types.CallbackQuery) -> None:
    """Показывает список целей для редактирования."""
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        goals = (await session.execute(select(Goal).where(Goal.user_id == db_user.id, Goal.status == GoalStatus.active))).scalars().all()
    
    if not goals:
        await cb.message.edit_text(
            "📝 Редактирование целей:\n\n"
            "У вас нет активных целей для редактирования.",
            reply_markup=back_main_menu(),
            parse_mode=None
        )
        await cb.answer()
        return
    
    # Создаем клавиатуру для выбора цели
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard_buttons = []
    for goal in goals:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"✏️ {goal.title[:30]}{'...' if len(goal.title) > 30 else ''}",
                callback_data=f"goal_edit:{goal.id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_goals")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await cb.message.edit_text(
        "📝 Редактирование целей:\n\n"
        "Выберите цель для редактирования:",
        reply_markup=keyboard,
        parse_mode=None
    )
    await cb.answer()


@router.callback_query(F.data.startswith("goal_edit:"))
async def goal_edit_select(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начинает редактирование выбранной цели."""
    goal_id = int(cb.data.split(":")[1])
    
    async with session_scope() as session:
        goal = (await session.execute(select(Goal).where(Goal.id == goal_id))).scalar_one()
        
        if not goal:
            await cb.answer("Цель не найдена!", show_alert=True)
            return
        
        # Сохраняем ID цели в состоянии
        await state.update_data(editing_goal_id=goal_id)
        await state.set_state(GoalFSM.waiting_title)
        
        text = (
            f"✏️ Редактирование цели:\n\n"
            f"Текущее название: {goal.title}\n\n"
            f"Введите новое название цели:"
        )
        
        await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode=None)
        await cb.answer()


@router.callback_query(F.data == "goals_reminders")
async def goals_reminders(cb: types.CallbackQuery) -> None:
    """Показывает настройки напоминаний для целей."""
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Получаем цели с напоминаниями
        reminders = (
            await session.execute(
                select(Goal, GoalReminder)
                .join(GoalReminder, Goal.id == GoalReminder.goal_id)
                .where(Goal.user_id == db_user.id, Goal.status == GoalStatus.active)
            )
        ).all()
        
        if not reminders:
            await cb.message.edit_text(
                "⏰ Напоминания по целям:\n\n"
                "У вас нет активных напоминаний по целям.\n\n"
                "Напоминания создаются автоматически при создании цели.",
                reply_markup=back_main_menu(),
                parse_mode=None
            )
            await cb.answer()
            return
        
        text = "⏰ Напоминания по целям:\n\n"
        
        for goal, reminder in reminders:
            text += f"🎯 {goal.title}\n"
            text += f"⏰ Время: {reminder.reminder_time}\n"
            text += f"📅 Срок: {goal.due_date.strftime('%d.%m.%Y') if goal.due_date else 'Не указан'}\n\n"
        
        text += "💡 Напоминания приходят ежедневно в указанное время с мотивирующими сообщениями!"
        
        await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode=None)
        await cb.answer()


@router.message(Command("test_reminder"))
async def test_reminder(message: types.Message) -> None:
    """Отправляет тестовое напоминание для проверки."""
    user = message.from_user
    if not user:
        return
    
    try:
        from app.services.goal_reminders import send_test_reminder
        
        await message.answer("🧪 Отправляю тестовое напоминание...")
        await send_test_reminder(user.id, "Тестовая цель", message.bot)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки тестового напоминания: {str(e)}")


