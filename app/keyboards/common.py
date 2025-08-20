from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Цели", callback_data="menu_goals"),
                InlineKeyboardButton(text="💰 Финансы", callback_data="menu_finance")
            ],
            [
                InlineKeyboardButton(text="🏆 Челленджи", callback_data="menu_challenges"),
                InlineKeyboardButton(text="🔥 Мотивация", callback_data="menu_motivation"),
                InlineKeyboardButton(text="📊 Анализ", callback_data="menu_analysis")
            ],
            [
                InlineKeyboardButton(text="🩺 Здоровье", callback_data="menu_health"),
                InlineKeyboardButton(text="🍽️ Питание", callback_data="menu_nutrition"),
                InlineKeyboardButton(text="📝 To-Do", callback_data="menu_todo")
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings")
            ],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
        ]
    )


def back_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]])


def goals_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📃 Список целей", callback_data="goals_list"),
                InlineKeyboardButton(text="➕ Добавить цель", callback_data="goals_add"),
                InlineKeyboardButton(text="✏️ Изменить цель", callback_data="goals_edit")
            ],
            [
                InlineKeyboardButton(text="📖 Подсказка SMART", callback_data="goals_smart_hint"),
                InlineKeyboardButton(text="⏰ Напоминания", callback_data="goals_reminders"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def challenges_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📃 Список", callback_data="ch_list"),
                InlineKeyboardButton(text="➕ Добавить", callback_data="ch_add"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def challenges_list_keyboard(ch_items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = []
    for ch_id, title in ch_items:
        rows.append(
            [
                InlineKeyboardButton(text=title, callback_data=f"ch_open:{ch_id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_challenges")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def challenge_detail_keyboard(ch_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отметить выполненным", callback_data=f"ch_done:{ch_id}"),
                InlineKeyboardButton(text="⏰ Изменить время", callback_data=f"ch_time:{ch_id}")
            ],
            [
                InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"ch_edit:{ch_id}"),
                InlineKeyboardButton(text="📅 Изменить дату окончания", callback_data=f"ch_edit_end_date:{ch_id}")
            ],
            [
                InlineKeyboardButton(text="🟢/🔴 Активен", callback_data=f"ch_toggle:{ch_id}"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ch_list")
            ],
        ]
    )


def settings_menu(current_tz: str | None) -> InlineKeyboardMarkup:
    tz_label = {
        "Europe/Moscow": "Москва",
        "Asia/Bishkek": "Бишкек",
    }.get(current_tz or "", "не выбрана")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"Текущая таймзона: {tz_label}", callback_data="noop"),
                InlineKeyboardButton(text="🇷🇺 Москва", callback_data="tz_moscow"),
                InlineKeyboardButton(text="🇰🇬 Бишкек", callback_data="tz_bishkek")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
        ]
    )





def finance_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Экспорт Excel", callback_data="finance_export_cb"),
                InlineKeyboardButton(text="📤 Импорт Excel", callback_data="finance_import_excel")
            ],
            [
                InlineKeyboardButton(text="📥 Загрузка CSV", callback_data="finance_upload_csv"),
                InlineKeyboardButton(text="➕ Добавить расход", callback_data="expense_add")
            ],
            [
                InlineKeyboardButton(text="💰 Доходы", callback_data="finance_income"),
                InlineKeyboardButton(text="💸 Кредиторы", callback_data="finance_creditors")
            ],
            [
                InlineKeyboardButton(text="🏦 Должники", callback_data="finance_debtors"),
                InlineKeyboardButton(text="🎯 Финансовые цели", callback_data="finance_goals")
            ],
            [
                InlineKeyboardButton(text="📊 Группировка по категориям", callback_data="finance_categories_groups")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def finance_upload_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏦 Альфа-Банк", callback_data="bank_alpha"),
                InlineKeyboardButton(text="🏦 Т-Банк", callback_data="bank_tbank")
            ],
            [
                InlineKeyboardButton(text="🏦 MBank", callback_data="bank_mbank")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")
            ],
        ]
    )


def finance_expense_menu() -> InlineKeyboardMarkup:
    """Меню для добавления расходов"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🛒 Покупки", callback_data="expense_category_purchases"),
                InlineKeyboardButton(text="🍽️ Питание", callback_data="expense_category_food")
            ],
            [
                InlineKeyboardButton(text="🚗 Транспорт", callback_data="expense_category_transport"),
                InlineKeyboardButton(text="🏠 Коммунальные", callback_data="expense_category_utilities")
            ],
            [
                InlineKeyboardButton(text="💊 Здоровье", callback_data="expense_category_health"),
                InlineKeyboardButton(text="🎭 Развлечения", callback_data="expense_category_entertainment")
            ],
            [
                InlineKeyboardButton(text="📱 Связь", callback_data="expense_category_communication"),
                InlineKeyboardButton(text="👕 Одежда", callback_data="expense_category_clothing")
            ],
            [
                InlineKeyboardButton(text="📚 Образование", callback_data="expense_category_education"),
                InlineKeyboardButton(text="🏦 Банковские", callback_data="expense_category_banking")
            ],
            [
                InlineKeyboardButton(text="🔧 Прочее", callback_data="expense_category_other"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")
            ],
        ]
    )


def finance_income_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Постоянный доход", callback_data="income_add_regular"),
                InlineKeyboardButton(text="➕ Внеплановый доход", callback_data="income_add_extra")
            ],
            [
                InlineKeyboardButton(text="📋 Список доходов", callback_data="income_list"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")
            ],
        ]
    )


def finance_goals_menu() -> InlineKeyboardMarkup:
    """Меню для управления финансовыми целями"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить цель", callback_data="financial_goal_add"),
                InlineKeyboardButton(text="📋 Мои цели", callback_data="financial_goals_list")
            ],
            [
                InlineKeyboardButton(text="💰 Пополнить цель", callback_data="financial_goal_contribute"),
                InlineKeyboardButton(text="📊 Прогресс", callback_data="financial_goals_progress")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")
            ],
        ]
    )


def creditor_debtor_menu(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    """Меню для кредитора или должника"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Изменить", callback_data=f"{item_type}_edit:{item_id}"),
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"{item_type}_delete:{item_id}")
            ],
            [
                InlineKeyboardButton(text="✅ Отметить выплату", callback_data=f"{item_type}_payment:{item_id}"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"menu_finance")
            ],
        ]
    )


def motivation_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👁 Видение", callback_data="mot_view"),
                InlineKeyboardButton(text="🎯 Годовая цель", callback_data="mot_year_goal"),
                InlineKeyboardButton(text="🧭 Миссия", callback_data="mot_mission")
            ],
            [
                InlineKeyboardButton(text="💎 Ценности", callback_data="mot_values"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data="mot_edit"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def motivation_edit_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👁 Изменить видение", callback_data="mot_edit_vision"),
                InlineKeyboardButton(text="🧭 Изменить миссию", callback_data="mot_edit_mission"),
                InlineKeyboardButton(text="💎 Изменить ценности", callback_data="mot_edit_values")
            ],
            [
                InlineKeyboardButton(text="🎯 Изменить годовую цель", callback_data="mot_edit_year_goal"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_motivation")
            ],
        ]
    )


def analysis_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Начать анализ недели", callback_data="analysis_start"),
                InlineKeyboardButton(text="📊 История анализов", callback_data="analysis_history"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def nutrition_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨‍🍳 Готовка сейчас", callback_data="nutrition_cooking_now"),
                InlineKeyboardButton(text="💪 Сушка/масса", callback_data="nutrition_body_recomp")
            ],
            [
                InlineKeyboardButton(text="💰 Бюджет питания", callback_data="nutrition_budget"),
                InlineKeyboardButton(text="⏰ Настройка времени", callback_data="nutrition_time_settings")
            ],
            [
                InlineKeyboardButton(text="📋 История готовки", callback_data="nutrition_history"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def goals_list_keyboard(goal_items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = []
    for goal_id, title in goal_items:
        rows.append(
            [
                InlineKeyboardButton(text=f"✅ {title}", callback_data=f"goal_done:{goal_id}"),
                InlineKeyboardButton(text="✖", callback_data=f"goal_cancel:{goal_id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_goals")])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def health_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 Трекинг показателей", callback_data="health_track_menu"),
                InlineKeyboardButton(text="🎯 Цели и привычки", callback_data="health_goals"),
                InlineKeyboardButton(text="📊 Аналитика", callback_data="health_analytics")
            ],
            [
                InlineKeyboardButton(text="🔔 Напоминания", callback_data="health_reminders"),
                InlineKeyboardButton(text="🔗 Интеграции", callback_data="health_integrations"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def health_track_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚶 Шаги", callback_data="health_track:steps"),
                InlineKeyboardButton(text="🔥 Калории", callback_data="health_track:calories"),
                InlineKeyboardButton(text="😴 Сон (мин)", callback_data="health_track:sleep")
            ],
            [
                InlineKeyboardButton(text="❤️ Пульс покоя", callback_data="health_track:hr"),
                InlineKeyboardButton(text="⚖️ Вес (кг)", callback_data="health_track:weight"),
                InlineKeyboardButton(text="🩸 Давление (сист/диаст)", callback_data="health_track:bp")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")],
        ]
    )


def todo_menu() -> InlineKeyboardMarkup:
    """Главное меню To-Do раздела"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить задачу", callback_data="todo_add"),
                InlineKeyboardButton(text="📋 Список задач", callback_data="todo_list")
            ],
            [
                InlineKeyboardButton(text="🔄 Ежедневные дела", callback_data="todo_daily"),
                InlineKeyboardButton(text="✏️ Изменить задачу", callback_data="todo_edit")
            ],
            [
                InlineKeyboardButton(text="🗑️ Удалить задачу", callback_data="todo_delete"),
                InlineKeyboardButton(text="✅ Отметить выполненной", callback_data="todo_complete")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def todo_priority_menu() -> InlineKeyboardMarkup:
    """Меню выбора приоритета для задачи"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔴 Высокий", callback_data="todo_priority_high"),
                InlineKeyboardButton(text="🟡 Средний", callback_data="todo_priority_medium")
            ],
            [
                InlineKeyboardButton(text="🟢 Низкий", callback_data="todo_priority_low"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="todo_add")
            ],
        ]
    )


def todo_edit_menu(todo_id: int) -> InlineKeyboardMarkup:
    """Меню редактирования задачи"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"todo_edit_title:{todo_id}"),
                InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"todo_edit_description:{todo_id}")
            ],
            [
                InlineKeyboardButton(text="📅 Изменить дату", callback_data=f"todo_edit_date:{todo_id}"),
                InlineKeyboardButton(text="🔴 Изменить приоритет", callback_data=f"todo_edit_priority:{todo_id}")
            ],
            [
                InlineKeyboardButton(text="🔄 Сделать ежедневной", callback_data=f"todo_toggle_daily:{todo_id}"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="todo_edit")
            ],
        ]
    )


def todo_list_keyboard(todos: list[tuple[int, str, bool]]) -> InlineKeyboardMarkup:
    """Клавиатура для списка задач"""
    rows = []
    for todo_id, title, is_completed in todos:
        status_icon = "✅" if is_completed else "⭕"
        rows.append(
            [
                InlineKeyboardButton(text=f"{status_icon} {title}", callback_data=f"todo_view:{todo_id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="todo_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def todo_view_keyboard(todo_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра задачи"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Изменить", callback_data=f"todo_edit_menu:{todo_id}"),
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"todo_delete_confirm:{todo_id}")
            ],
            [
                InlineKeyboardButton(text="✅ Выполнить", callback_data=f"todo_mark_complete:{todo_id}"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="todo_list")
            ],
        ]
    )


def todo_daily_reminder_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для вечернего напоминания о составлении To-Do"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить задачу на завтра", callback_data="todo_add_tomorrow"),
                InlineKeyboardButton(text="📋 Посмотреть завтрашние дела", callback_data="todo_view_tomorrow")
            ],
            [
                InlineKeyboardButton(text="🔄 Копировать сегодняшние", callback_data="todo_copy_today"),
                InlineKeyboardButton(text="⏰ Напомнить позже", callback_data="todo_remind_later")
            ],
        ]
    )


def todo_type_menu() -> InlineKeyboardMarkup:
    """Меню выбора типа задачи (разовая или ежедневная)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Разовая задача", callback_data="todo_type_single"),
                InlineKeyboardButton(text="🔄 Ежедневная задача", callback_data="todo_type_daily")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_todo")
            ],
        ]
    )
