from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Цели", callback_data="menu_goals"),
                InlineKeyboardButton(text="🔁 Привычки", callback_data="menu_habits"),
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
                InlineKeyboardButton(text="⏰ Изменить время", callback_data=f"ch_time:{ch_id}"),
                InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"ch_edit:{ch_id}")
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


def habits_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Инициализировать базовые", callback_data="habits_init"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
            ],
        ]
    )


def finance_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Экспорт Excel", callback_data="finance_export_cb"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")
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
                InlineKeyboardButton(text="💪 Сушка/масса", callback_data="nutrition_body_recomp"),
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
