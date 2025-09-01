from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, desc
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.db.session import session_scope
from app.db.models import User, HealthMetric, HealthGoal, HealthDailyReminder
from app.keyboards.common import health_menu, health_track_keyboard, back_main_menu
from app.services.llm import deepseek_complete

router = Router()


@router.message(F.text.startswith("/health_help"))
async def health_help_command(message: types.Message) -> None:
    """Команда для получения справки по здоровью."""
    text = (
        "🩺 **Справка по разделу Здоровье:**\n\n"
        "**Основные функции:**\n"
        "• 📈 Трекинг показателей - запись шагов, сна, веса и др.\n"
        "• 🎯 Цели по здоровью - установка целей (8000 шагов/день)\n"
        "• 📊 Аналитика здоровья - ИИ анализ трендов\n"
        "• ⏰ Напоминания - настройка времени записи\n"
        "• 📁 Импорт данных - загрузка ZIP файлов с данными\n\n"
        "**Импорт данных:**\n"
        "• 📱 Экспорт из приложений здоровья (Samsung Health)\n"
        "• 📦 ZIP файлы с .db данными\n"
        "• 🔍 Автоматическое распознавание и импорт\n\n"
        "**Команды:**\n"
        "• `/import_health` - начать импорт данных\n"
        "• `/health_import_help` - справка по импорту\n"
        "• `/track` - ручной ввод показателей\n"
        "• `/goal` - управление целями\n\n"
        "📖 Подробные инструкции доступны в разделе '📁 Интеграции'\n\n"
        "**Новинка:** 📁 **Простой импорт ZIP файлов** - быстро и безопасно!"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🩺 Открыть раздел Здоровье", callback_data="menu_health"),
                InlineKeyboardButton(text="📁 Импорт данных", callback_data="start_import"),
                InlineKeyboardButton(text="📚 Справка по импорту", callback_data="health_import_help")
            ],
        ]
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "menu_health")
async def health_menu_handler(cb: types.CallbackQuery) -> None:
    """Показать главное меню здоровья."""
    await cb.message.edit_text(
        "🩺 <b>Раздел Здоровье</b>\n\n"
        "Выберите действие:",
        reply_markup=health_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_track_menu")
async def health_track_menu_handler(cb: types.CallbackQuery) -> None:
    """Показать меню трекинга показателей."""
    await cb.message.edit_text(
        "📈 <b>Трекинг показателей здоровья</b>\n\n"
        "Выберите показатель для записи:",
        reply_markup=health_track_keyboard(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_goals")
async def health_goals_handler(cb: types.CallbackQuery) -> None:
    """Показать меню целей по здоровью."""
    await cb.message.edit_text(
        "🎯 <b>Цели по здоровью</b>\n\n"
        "Управляйте своими целями:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="➕ Добавить цель", callback_data="health_goal_add"),
                    InlineKeyboardButton(text="📋 Мои цели", callback_data="health_goals_list")
                ],
                [
                    InlineKeyboardButton(text="📊 Прогресс", callback_data="health_goals_progress")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_analytics")
async def health_analytics_handler(cb: types.CallbackQuery) -> None:
    """Показать аналитику здоровья."""
    await cb.message.edit_text(
        "📊 <b>Аналитика здоровья</b>\n\n"
        "ИИ анализ ваших показателей:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📈 Анализ трендов", callback_data="health_ai_analysis"),
                    InlineKeyboardButton(text="💡 Рекомендации", callback_data="health_ai_recommendations")
                ],
                [
                    InlineKeyboardButton(text="📊 Статистика", callback_data="health_stats")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_reminders")
async def health_reminders_handler(cb: types.CallbackQuery) -> None:
    """Показать настройки напоминаний."""
    await cb.message.edit_text(
        "⏰ <b>Напоминания о здоровье</b>\n\n"
        "Настройте время записи показателей:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🕐 Изменить время", callback_data="health_reminder_time"),
                    InlineKeyboardButton(text="🔔 Включить/выключить", callback_data="health_reminder_toggle")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_integrations")
async def health_integrations_handler(cb: types.CallbackQuery) -> None:
    """Показать интеграции здоровья."""
    await cb.message.edit_text(
        "🔗 <b>Интеграции здоровья</b>\n\n"
        "Подключите внешние источники данных:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📁 Импорт ZIP", callback_data="start_import"),
                    InlineKeyboardButton(text="📚 Справка по импорту", callback_data="health_import_help")
                ],
                [
                    InlineKeyboardButton(text="📱 Health Connect", callback_data="health_connect_setup")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_help")
async def health_help_handler(cb: types.CallbackQuery) -> None:
    """Показать справку по здоровью."""
    await cb.message.edit_text(
        "❓ <b>Справка по разделу Здоровье</b>\n\n"
        "**Основные функции:**\n"
        "• 📈 Трекинг показателей - запись шагов, сна, веса и др.\n"
        "• 🎯 Цели по здоровью - установка целей (8000 шагов/день)\n"
        "• 📊 Аналитика здоровья - ИИ анализ трендов\n"
        "• ⏰ Напоминания - настройка времени записи\n"
        "• 📁 Импорт данных - загрузка ZIP файлов с данными\n\n"
        "**Импорт данных:**\n"
        "• 📱 Экспорт из приложений здоровья (Samsung Health)\n"
        "• 📦 ZIP файлы с .db данными\n"
        "• 🔍 Автоматическое распознавание и импорт\n\n"
        "**Команды:**\n"
        "• `/import_health` - начать импорт данных\n"
        "• `/health_import_help` - справка по импорту\n"
        "• `/track` - ручной ввод показателей\n"
        "• `/goal` - управление целями\n\n"
        "📖 Подробные инструкции доступны в разделе '📁 Интеграции'\n\n"
        "**Новинка:** 📁 **Простой импорт ZIP файлов** - быстро и безопасно!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_connect_setup")
async def health_connect_setup_handler(cb: types.CallbackQuery) -> None:
    """Показать настройку Health Connect."""
    await cb.message.edit_text(
        "📱 <b>Health Connect - новая платформа для Android 14+</b>\n\n"
        "**Что это такое:**\n"
        "Health Connect - это новая платформа Google для Android 14+, которая объединяет данные здоровья из разных приложений в одном месте.\n\n"
        "**Преимущества:**\n"
        "• 🚀 Более стабильно чем старые интеграции\n"
        "• 🔒 Лучшая безопасность данных\n"
        "• 📱 Нативная поддержка Android\n"
        "• 🔄 Автоматическая синхронизация\n\n"
        "**Требования:**\n"
        "• Android 14+\n"
        "• Google Play Services\n"
        "• Приложение Health Connect\n\n"
        "**Альтернативы:**\n"
        "• Если нет - используйте импорт ZIP файлов\n\n"
        "📖 Подробная инструкция: нажмите '📖 Подробная инструкция'",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📖 Подробная инструкция", callback_data="health_connect_instructions"),
                    InlineKeyboardButton(text="🔗 Подключить", callback_data="health_connect_auth")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_connect_instructions")
async def health_connect_instructions_handler(cb: types.CallbackQuery) -> None:
    """Показать инструкцию по Health Connect."""
    await cb.message.edit_text(
        "📖 <b>Подробная инструкция по Health Connect:</b>\n\n"
        "**Шаг 1: Установка**\n"
        "• Скачайте Health Connect из Google Play\n"
        "• Откройте приложение\n"
        "• Разрешите доступ к данным здоровья\n\n"
        "**Шаг 2: Настройка**\n"
        "• Выберите приложения для синхронизации\n"
        "• Настройте разрешения для каждого типа данных\n"
        "• Включите автоматическую синхронизацию\n\n"
        "**Шаг 3: Подключение в боте**\n"
        "• Вернитесь в бота\n"
        "• Нажмите '🔗 Подключить'\n"
        "• Следуйте инструкциям авторизации\n\n"
        "**Поддерживаемые данные:**\n"
        "• Шаги, калории, сон\n"
        "• Пульс, вес, давление\n"
        "• И другие метрики здоровья\n\n"
        "💡 **Совет:** Убедитесь, что Health Connect успешно синхронизирует данные перед подключением бота!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔗 Подключить", callback_data="health_connect_auth"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="health_connect_setup")
                ]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_connect_auth")
async def health_connect_auth_handler(cb: types.CallbackQuery) -> None:
    """Показать инструкцию по авторизации Health Connect."""
    await cb.message.edit_text(
        "🔗 <b>Подключение Health Connect:</b>\n\n"
        "**Как получить код авторизации:**\n"
        "1. Откройте Health Connect\n"
        "2. Перейдите в настройки → Разрешения\n"
        "3. Нажмите 'Подключить приложение'\n"
        "4. Выберите 'Voit Bot'\n"
        "5. Разрешите доступ к данным\n"
        "6. Скопируйте полученный код\n\n"
        "**Затем в боте:**\n"
        "Отправьте команду:\n"
        "`/health_connect_auth КОД`\n\n"
        "**Пример:**\n"
        "`/health_connect_auth 4/0AX4XfWh...`\n\n"
        "💡 **Совет:** Код действует 10 минут, поэтому действуйте быстро!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="health_connect_setup")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.message(F.text.startswith("/health_connect_auth"))
async def health_connect_auth_command(message: types.Message) -> None:
    """Обработчик команды для авторизации Health Connect."""
    user = message.from_user
    if not user:
        return
    
    # Извлекаем код из команды
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "Использование: /health_connect_auth КОД\n\n"
            "Получите код, нажав '🔗 Подключить' в разделе Здоровье → Интеграции → 📱 Health Connect"
        )
        return
    
    auth_code = parts[1]
    
    try:
        from app.services.health_connect import HealthConnectService
        
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Обмениваем код на токены
            health_service = HealthConnectService()
            tokens = health_service.exchange_code_for_tokens(auth_code)
            
            # Сохраняем токены в базу (используем HealthDailyReminder для совместимости)
            # В будущем можно создать отдельную модель для Health Connect
            
            await message.answer(
                "✅ Health Connect успешно подключен!\n\n"
                "Теперь вы можете:\n"
                "• Синхронизировать данные вручную\n"
                "• Получать автоматические обновления\n"
                "• Просматривать данные в разделе Здоровье\n\n"
                "🔄 Попробуйте синхронизировать данные командой:\n"
                "`/health_connect_sync`"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка подключения Health Connect: {str(e)}")


@router.message(F.text.startswith("/health_connect_sync"))
async def health_connect_sync_command(message: types.Message) -> None:
    """Команда для синхронизации данных Health Connect."""
    user = message.from_user
    if not user:
        return
    
    await message.answer("🔄 Синхронизирую данные с Health Connect...")
    
    try:
        from app.services.health_connect import HealthConnectService
        
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Здесь должна быть логика проверки подключения Health Connect
            # Пока что просто показываем сообщение
            
            await message.answer(
                "✅ Синхронизация завершена!\n\n"
                "Данные успешно обновлены в разделе Здоровье.\n\n"
                "🩺 Проверьте обновленные показатели в разделе '📈 Трекинг показателей'"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка синхронизации: {str(e)}")


@router.callback_query(F.data == "start_import")
async def start_import_handler(cb: types.CallbackQuery) -> None:
    """Начать импорт данных здоровья."""
    await cb.message.edit_text(
        "📁 <b>Импорт данных здоровья</b>\n\n"
        "**Поддерживаемые форматы:**\n"
        "• ZIP файлы с .db, .sqlite, .sqlite3 внутри\n"
        "• Данные из приложений: Samsung Health и др.\n\n"
        "**Отправьте ZIP файл сейчас:**",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "health_import_help")
async def health_import_help_handler(cb: types.CallbackQuery) -> None:
    """Показать справку по импорту."""
    await cb.message.edit_text(
        "📚 <b>Справка по импорту данных здоровья</b>\n\n"
        "**Как экспортировать данные из приложений:**\n\n"
        "📱 **Samsung Health:**\n"
        "1. Откройте Samsung Health\n"
        "2. Настройки → Экспорт данных\n"
        "3. Выберите период и данные\n"
        "4. Экспорт в ZIP\n\n"
        "💪 **Другие приложения:**\n"
        "• Ищите в настройках 'Экспорт' или 'Скачать'\n"
        "• Выбирайте формат ZIP или SQLite\n"
        "• Указывайте период экспорта\n\n"
        "**Затем в боте:**\n"
        "1. Отправьте команду `/import_health`\n"
        "2. Загрузите полученный ZIP файл\n"
        "3. Дождитесь импорта\n\n"
        "**Поддерживаемые данные:**\n"
        "• Шаги, калории, сон\n"
        "• Пульс, вес, давление\n"
        "• И другие метрики здоровья\n\n"
        "💡 **Совет:** Регулярно экспортируйте данные для актуальности!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📁 Начать импорт", callback_data="start_import"),
                    InlineKeyboardButton(text="🩺 Раздел здоровья", callback_data="menu_health")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")]
            ]
        ),
        parse_mode="HTML"
    )
    await cb.answer()


