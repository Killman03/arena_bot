#!/usr/bin/env python3
"""
Обработчик для импорта данных здоровья из ZIP файлов.
Пользователь загружает ZIP файл, бот извлекает .db файл и импортирует данные.
"""

import os
import tempfile
from typing import Optional
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User
from app.services.zip_importer import ZipImporterService
from app.keyboards.common import back_main_menu

router = Router()


class ZipImportFSM(StatesGroup):
    waiting_for_zip = State()


@router.message(F.text.startswith("/import_health"))
async def import_health_start(message: types.Message, state: FSMContext) -> None:
    """Начинает процесс импорта данных здоровья."""
    user = message.from_user
    if not user:
        return
    
    await state.set_state(ZipImportFSM.waiting_for_zip)
    
    text = (
        "📁 **Импорт данных здоровья из ZIP файла**\n\n"
        "**Как это работает:**\n"
        "1. 📱 Приложение здоровья экспортирует данные в ZIP\n"
        "2. 📤 Вы загружаете ZIP файл в этот чат\n"
        "3. 🔍 Бот извлекает .db файл из ZIP\n"
        "4. 📊 Импортирует данные в ваш профиль\n\n"
        "**Поддерживаемые форматы:**\n"
        "• ZIP файлы с .db, .sqlite, .sqlite3 внутри\n"
        "• Данные из приложений: Samsung Health и др.\n\n"
        "**Отправьте ZIP файл сейчас:**"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_import")],
        ]
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.message(ZipImportFSM.waiting_for_zip, F.document)
async def handle_zip_upload(message: types.Message, state: FSMContext) -> None:
    """Обрабатывает загруженный ZIP файл."""
    user = message.from_user
    if not user:
        return
    
    document = message.document
    
    # Проверяем, что это ZIP файл
    if not document.file_name.lower().endswith('.zip'):
        await message.answer(
            "❌ **Ошибка:** Файл должен быть в формате .zip\n\n"
            "Пожалуйста, загрузите ZIP файл с данными здоровья."
        )
        return
    
    await message.answer("📥 Загружаю ZIP файл...")
    
    try:
        # Скачиваем файл
        file_path = await download_document(document)
        
        if not file_path:
            await message.answer("❌ Ошибка загрузки файла. Попробуйте снова.")
            await state.clear()
            return
        
        # Импортируем данные
        await message.answer("🔄 Импортирую данные...")
        
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == user.id)
            )).scalar_one()
            
            if not db_user:
                await message.answer("❌ Пользователь не найден в базе данных.")
                await state.clear()
                return
            
            # Импортируем данные
            importer = ZipImporterService()
            result = await importer.import_health_data_from_zip(
                session, db_user.id, file_path
            )
            
            if result['success']:
                # Успешный импорт
                text = (
                    "✅ **Данные успешно импортированы!**\n\n"
                    f"📊 **Результат импорта:**\n"
                    f"• Записей импортировано: {result['total_records']}\n"
                    f"• Таблиц обработано: {len(result['tables_imported'])}\n"
                    f"• Таблицы: {', '.join(result['tables_imported'])}\n\n"
                    "🎯 Теперь вы можете:\n"
                    "• Просматривать данные в разделе 'Здоровье'\n"
                    "• Анализировать тренды\n"
                    "• Устанавливать цели\n\n"
                    "📁 Файл автоматически удален для безопасности."
                )
                
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🩺 Открыть здоровье", callback_data="menu_health"),
                            InlineKeyboardButton(text="📊 Аналитика", callback_data="health_analytics")
                        ],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start")]
                    ]
                )
                
                await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
                
            else:
                # Ошибка импорта
                await message.answer(
                    f"❌ **Ошибка импорта:**\n\n"
                    f"{result['error']}\n\n"
                    "💡 **Возможные причины:**\n"
                    "• ZIP файл поврежден\n"
                    "• Внутри нет .db файла\n"
                    "• Неправильная структура данных\n\n"
                    "Попробуйте другой файл или обратитесь к инструкции."
                )
        
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        await message.answer(
            f"❌ **Произошла ошибка:**\n\n"
            f"{str(e)}\n\n"
            "Попробуйте снова или обратитесь к администратору."
        )
    
    finally:
        await state.clear()


@router.message(ZipImportFSM.waiting_for_zip)
async def handle_wrong_file_type(message: types.Message) -> None:
    """Обрабатывает неправильный тип файла."""
    await message.answer(
        "❌ **Пожалуйста, загрузите ZIP файл!**\n\n"
        "Вы отправили текст, но нужен ZIP файл с данными здоровья.\n\n"
        "**Или нажмите 'Отмена' для возврата в главное меню.**"
    )


@router.callback_query(F.data == "cancel_import")
async def cancel_import(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Отменяет процесс импорта."""
    await state.clear()
    await cb.message.edit_text(
        "❌ Импорт отменен.\n\n"
        "Вы можете попробовать снова командой /import_health"
    )
    await cb.answer()


@router.message(F.text.startswith("/health_import_help"))
async def health_import_help(message: types.Message) -> None:
    """Показывает справку по импорту данных здоровья."""
    text = (
        "📚 **Справка по импорту данных здоровья**\n\n"
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
        "💡 **Совет:** Регулярно экспортируйте данные для актуальности!"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📁 Начать импорт", callback_data="start_import"),
                InlineKeyboardButton(text="🩺 Раздел здоровья", callback_data="menu_health")
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start")]
        ]
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "start_import")
async def start_import_callback(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начинает импорт через callback."""
    await import_health_start(cb.message, state)
    await cb.answer()


async def download_document(document: types.Document) -> Optional[str]:
    """Скачивает документ во временный файл."""
    try:
        # Создаем временный файл
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_path = temp_file.name
        temp_file.close()
        
        # Скачиваем файл
        file_info = await document.bot.get_file(document.file_id)
        await document.bot.download_file(file_info.file_path, temp_path)
        
        return temp_path
        
    except Exception as e:
        # Очищаем временный файл в случае ошибки
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise e
