from __future__ import annotations

import asyncio
from typing import Optional
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State

from sqlalchemy import select
from app.db.session import session_scope
from app.db.models import User
from app.utils.timezone_utils import COMMON_TIMEZONES, validate_timezone, get_timezone_display_name
from app.keyboards.common import settings_menu

router = Router()


# Состояния для FSM
SELECTING_TIMEZONE = "selecting_timezone"


@router.message(F.text == "/timezone")
async def timezone_command(message: types.Message) -> None:
    """Команда для настройки часового пояса"""
    await message.answer(
        "🌍 <b>Настройка часового пояса</b>\n\n"
        "Выберите ваш часовой пояс для корректной работы напоминаний:",
        reply_markup=create_timezone_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("timezone_"))
async def timezone_selection(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора часового пояса"""
    timezone_str = cb.data.replace("timezone_", "")
    
    if timezone_str == "custom":
        from app.keyboards.common import back_main_menu
        print(f"DEBUG: Устанавливаем состояние SELECTING_TIMEZONE для пользователя {cb.from_user.id}")
        
        await cb.message.edit_text(
            "✍️ <b>Введите ваш часовой пояс</b>\n\n"
            "Примеры:\n"
            "• <code>Europe/Moscow</code>\n"
            "• <code>America/New_York</code>\n"
            "• <code>Asia/Tokyo</code>\n"
            "• <code>UTC+3</code>\n"
            "• <code>UTC-5</code>\n\n"
            "Или нажмите кнопку для возврата к выбору из списка.",
            reply_markup=back_main_menu(),
            parse_mode="HTML"
        )
        
        await state.set_state(SELECTING_TIMEZONE)
        print(f"DEBUG: Состояние установлено: {await state.get_state()}")
        
        # Проверяем, что состояние действительно установлено
        await asyncio.sleep(0.1)  # Небольшая задержка
        final_state = await state.get_state()
        print(f"DEBUG: Финальное состояние после установки: {final_state}")
        
        await cb.answer()
        return
    
    # Сохраняем выбранный часовой пояс
    await save_user_timezone(cb.from_user.id, timezone_str)
    
    display_name = get_timezone_display_name(timezone_str)
    await cb.message.edit_text(
        f"✅ <b>Часовой пояс обновлен!</b>\n\n"
        f"🌍 <b>Выбранный пояс:</b> {display_name}\n\n"
        f"Теперь все напоминания будут приходить в соответствии с вашим местным временем.",
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(lambda message: True)
async def process_custom_timezone(message: types.Message, state: FSMContext) -> None:
    """Обработка ввода пользовательского часового пояса"""
    current_state = await state.get_state()
    print(f"DEBUG: 🎯 FSM Обработчик process_custom_timezone вызван!")
    print(f"DEBUG: 🎯 Текущее состояние: {current_state}")
    print(f"DEBUG: 🎯 Пользователь: {message.from_user.id}")
    print(f"DEBUG: 🎯 Текст сообщения: '{message.text}'")
    
    # Проверяем, что мы в правильном состоянии
    if current_state != SELECTING_TIMEZONE:
        print(f"DEBUG: 🎯 Неправильное состояние: {current_state}, ожидалось: {SELECTING_TIMEZONE}")
        return
    
    print(f"DEBUG: 🎯 Состояние правильное, обрабатываем ввод часового пояса")
    
    timezone_input = message.text.strip()
    
    # Добавляем отладочную информацию
    print(f"DEBUG: Пользователь ввел часовой пояс: '{timezone_input}'")
    print(f"DEBUG: Валидация UTC формата: {timezone_input.startswith('UTC')}")
    
    if timezone_input.startswith("UTC"):
        offset = parse_utc_offset(timezone_input)
        print(f"DEBUG: UTC смещение: {offset}")
        is_valid = offset is not None
    else:
        try:
            import pytz
            pytz.timezone(timezone_input)
            is_valid = True
            print(f"DEBUG: Стандартный часовой пояс валиден")
        except Exception as e:
            is_valid = False
            print(f"DEBUG: Ошибка валидации: {e}")
    
    print(f"DEBUG: Итоговая валидация: {is_valid}")
    
    # Проверяем валидность часового пояса
    if is_valid:
        try:
            await save_user_timezone(message.from_user.id, timezone_input)
            print(f"DEBUG: Часовой пояс сохранен в БД")
            
            await message.answer(
                f"✅ <b>Часовой пояс обновлен!</b>\n\n"
                f"🌍 <b>Выбранный пояс:</b> {timezone_input}\n\n"
                f"Теперь все напоминания будут приходить в соответствии с вашим местным временем.",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"DEBUG: Ошибка сохранения: {e}")
            await message.answer(
                f"❌ <b>Ошибка сохранения часового пояса</b>\n\n"
                f"Ошибка: {str(e)}\n\n"
                f"Попробуйте еще раз или обратитесь к администратору.",
                parse_mode="HTML"
            )
    else:
        await message.answer(
            "❌ <b>Неверный формат часового пояса</b>\n\n"
            f"Вы ввели: <code>{timezone_input}</code>\n\n"
            "Пожалуйста, используйте один из форматов:\n"
            "• <code>Europe/Moscow</code>\n"
            "• <code>UTC+3</code>\n"
            "• <code>UTC-5</code>\n"
            "• <code>America/New_York</code>\n"
            "• <code>Asia/Tokyo</code>\n\n"
            "Попробуйте еще раз или выберите из списка командой /timezone",
            parse_mode="HTML"
        )
    
    await state.clear()


@router.message(F.text == "/mytimezone")
async def show_current_timezone(message: types.Message) -> None:
    """Показать текущий часовой пояс пользователя"""
    async with session_scope() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )).scalar_one()
        
        if user.timezone:
            display_name = get_timezone_display_name(user.timezone)
            await message.answer(
                f"🌍 <b>Ваш текущий часовой пояс:</b>\n\n"
                f"📍 {display_name}\n\n"
                f"Изменить можно командой /timezone",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "🌍 <b>Часовой пояс не настроен</b>\n\n"
                "Настройте часовой пояс командой /timezone для корректной работы напоминаний.",
                parse_mode="HTML"
            )


def create_timezone_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора часового пояса"""
    keyboard = []
    
    # Группируем часовые пояса по регионам
    regions = {
        "🇷🇺 Россия и СНГ": ["Europe/Moscow", "Asia/Almaty", "Asia/Tashkent"],
        "🇪🇺 Европа": ["Europe/London", "Europe/Berlin", "Europe/Paris"],
        "🇺🇸 Америка": ["America/New_York", "America/Los_Angeles", "America/Chicago"],
        "🌏 Азия": ["Asia/Tokyo", "Asia/Shanghai", "Asia/Dubai"],
        "🇦🇺 Австралия": ["Australia/Sydney", "Australia/Perth"]
    }
    
    for region_name, timezones in regions.items():
        keyboard.append([InlineKeyboardButton(text=region_name, callback_data="noop")])
        row = []
        for tz in timezones:
            display_name = get_timezone_display_name(tz)
            row.append(InlineKeyboardButton(text=display_name, callback_data=f"timezone_{tz}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:  # Добавляем оставшиеся кнопки
            keyboard.append(row)
    
    # Кнопка для пользовательского ввода
    keyboard.append([InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="timezone_custom")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def save_user_timezone(telegram_id: int, timezone_str: str) -> None:
    """Сохраняет часовой пояс пользователя в базе данных"""
    async with session_scope() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )).scalar_one()
        
        user.timezone = timezone_str
        await session.commit()


def parse_utc_offset(timezone_str: str) -> Optional[int]:
    """
    Парсит строку формата UTC+3, UTC-5 и возвращает смещение в часах.
    
    Args:
        timezone_str: Строка в формате UTC+3, UTC-5, UTC+3:30 и т.д.
    
    Returns:
        Смещение в часах (может быть дробным для UTC+3:30)
    """
    import re
    
    # Паттерн для UTC+3, UTC-5, UTC+3:30
    pattern = r'^UTC([+-])(\d{1,2})(?::(\d{2}))?$'
    match = re.match(pattern, timezone_str)
    
    if match:
        sign = match.group(1)
        hours = int(match.group(2))
        minutes = int(match.group(3)) if match.group(3) else 0
        
        # Конвертируем минуты в часы
        total_hours = hours + (minutes / 60)
        
        if sign == '-':
            total_hours = -total_hours
        
        return int(total_hours)
    
    return None


@router.callback_query(F.data == "menu_settings")
async def settings_menu_handler(cb: types.CallbackQuery) -> None:
    """Обработчик кнопки Настройки в главном меню"""
    await cb.message.edit_text(
        "⚙️ <b>Настройки</b>\n\n"
        "Выберите, что хотите настроить:",
        reply_markup=settings_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "settings_timezone")
async def settings_timezone_handler(cb: types.CallbackQuery) -> None:
    """Обработчик кнопки Выбрать таймзону в настройках"""
    await cb.message.edit_text(
        "🌍 <b>Настройка часового пояса</b>\n\n"
        "Выберите ваш часовой пояс для корректной работы напоминаний:",
        reply_markup=create_timezone_keyboard(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "noop")
async def noop_handler(cb: types.CallbackQuery) -> None:
    """Обработчик для кнопок-заголовков"""
    await cb.answer("Выберите часовой пояс из списка ниже")


# Убираем общий обработчик сообщений полностью, чтобы не конфликтовать с FSM


@router.callback_query(F.data == "back_main")
async def back_main_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик кнопки Назад"""
    current_state = await state.get_state()
    print(f"DEBUG: Кнопка Назад нажата, текущее состояние: {current_state}")
    
    if current_state == SELECTING_TIMEZONE:
        # Очищаем состояние и возвращаемся к выбору часового пояса
        await state.clear()
        print(f"DEBUG: Состояние очищено")
        
        await cb.message.edit_text(
            "🌍 <b>Настройка часового пояса</b>\n\n"
            "Выберите ваш часовой пояс для корректной работы напоминаний:",
            reply_markup=create_timezone_keyboard(),
            parse_mode="HTML"
        )
    else:
        # Возвращаемся в главное меню
        from app.keyboards.common import main_menu
        await cb.message.edit_text(
            "🏠 <b>Главное меню</b>\n\n"
            "Выберите раздел для работы:",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
    
    await cb.answer()
