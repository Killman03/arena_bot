from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, desc
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.db.session import session_scope
from app.db.models import User, HealthMetric, HealthGoal, HealthDailyReminder, GoogleFitToken
from app.keyboards.common import health_menu, health_track_keyboard, back_main_menu
from app.services.llm import deepseek_complete
from app.services.google_drive import GoogleDriveService


router = Router()


@router.message(F.text.startswith("/google_fit_auth"))
async def google_fit_auth_command(message: types.Message) -> None:
    """Обработчик команды для авторизации Google Fit."""
    user = message.from_user
    if not user:
        return
    
    # Извлекаем код из команды
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "Использование: /google_fit_auth КОД\n\n"
            "Получите код, нажав 'Google Fit (прямая интеграция)' в разделе Здоровье → Интеграции"
        )
        return
    
    auth_code = parts[1]
    
    try:
        from app.services.google_fit import GoogleFitService
        
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Обмениваем код на токены
            google_service = GoogleFitService()
            tokens = google_service.exchange_code_for_tokens(auth_code)
            
            # Сохраняем токены в базу
            google_token = GoogleFitToken(
                user_id=db_user.id,
                integration_type="google_fit",
                access_token=tokens['token'],
                refresh_token=tokens.get('refresh_token'),
                token_uri=tokens['token_uri'],
                client_id=tokens['client_id'],
                client_secret=tokens['client_secret'],
                scopes=','.join(tokens['scopes'])
            )
            session.add(google_token)
            await session.commit()
            
            await message.answer(
                "✅ Google Fit успешно подключен!\n\n"
                "Теперь вы можете:\n"
                "• Синхронизировать данные вручную\n"
                "• Получать автоматические обновления\n"
                "• Просматривать данные в разделе Здоровье"
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка подключения Google Fit: {str(e)}")


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
        "• 🔗 Интеграции - подключение Google Fit/Drive\n\n"
        "**Интеграции с данными:**\n"
        "• 🔗 Google Fit - прямая интеграция\n"
        "• 📁 Google Drive - через Health Sync (рекомендуется)\n\n"
        "**Команды:**\n"
        "• `/google_fit_auth КОД` - подключение Google Fit\n"
        "• `/google_drive_auth КОД` - подключение Google Drive\n\n"
        "📖 Подробные инструкции доступны в разделе '🔗 Интеграции'"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🩺 Открыть раздел Здоровье", callback_data="menu_health"),
                InlineKeyboardButton(text="📖 Инструкция Google Drive", callback_data="google_drive_instructions"),
                InlineKeyboardButton(text="❓ Частые вопросы", callback_data="google_drive_faq")
            ],
        ]
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@router.message(F.text.startswith("/google_drive_auth"))
async def google_drive_auth_command(message: types.Message) -> None:
    """Обработчик команды для авторизации Google Drive."""
    user = message.from_user
    if not user:
        return
    
    # Извлекаем код из команды
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "Использование: /google_drive_auth КОД\n\n"
            "Получите код, нажав 'Google Drive (через Health Sync)' в разделе Здоровье → Интеграции\n\n"
            "📖 Подробная инструкция: нажмите '📖 Подробная инструкция Google Drive' в разделе интеграций"
        )
        return
    
    auth_code = parts[1]
    
    try:
        from app.services.google_drive import GoogleDriveService
        
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Обмениваем код на токены
            google_service = GoogleDriveService()
            tokens = google_service.exchange_code_for_tokens(auth_code)
            
            # Сохраняем токены в базу
            google_token = GoogleFitToken(
                user_id=db_user.id,
                integration_type="google_drive",
                access_token=tokens['token'],
                refresh_token=tokens.get('refresh_token'),
                token_uri=tokens['token_uri'],
                client_id=tokens['client_id'],
                client_secret=tokens['client_secret'],
                scopes=','.join(tokens['scopes'])
            )
            session.add(google_token)
            await session.commit()
            
            # Проверяем, есть ли файлы с данными
            try:
                credentials_dict = {
                    'token': tokens['token'],
                    'refresh_token': tokens.get('refresh_token'),
                    'token_uri': tokens['token_uri'],
                    'client_id': tokens['client_id'],
                    'client_secret': tokens['client_secret'],
                    'scopes': tokens['scopes']
                }
                
                files = await google_service.find_health_files(session, db_user.id, credentials_dict)
                
                if files:
                    await message.answer(
                        "✅ Google Drive успешно подключен!\n\n"
                        f"📁 Найдено файлов с данными: {len(files)}\n"
                        f"📄 Последний файл: {files[0]['name']}\n\n"
                        "Теперь вы можете:\n"
                        "• Синхронизировать данные из файлов Health Sync\n"
                        "• Получать автоматические обновления каждые 6 часов\n"
                        "• Просматривать данные в разделе Здоровье\n\n"
                        "🔄 Попробуйте синхронизировать данные сейчас в разделе '🔗 Интеграции'!"
                    )
                else:
                    await message.answer(
                        "✅ Google Drive успешно подключен!\n\n"
                        "⚠️ **Внимание:** Файлы с данными здоровья не найдены\n\n"
                        "Убедитесь, что:\n"
                        "• Health Sync установлен и настроен\n"
                        "• Экспорт данных на Google Drive включен\n"
                        "• Есть хотя бы один файл с данными\n\n"
                        "📖 Подробная инструкция: нажмите '📖 Подробная инструкция Google Drive' в разделе интеграций"
                    )
                    
            except Exception as check_error:
                await message.answer(
                    "✅ Google Drive успешно подключен!\n\n"
                    "Теперь вы можете:\n"
                    "• Синхронизировать данные из файлов Health Sync\n"
                    "• Получать автоматические обновления\n"
                    "• Просматривать данные в разделе Здоровье\n\n"
                    "🔄 Попробуйте синхронизировать данные сейчас в разделе '🔗 Интеграции'!"
                )
            
    except Exception as e:
        error_message = str(e)
        if "invalid_grant" in error_message.lower():
            await message.answer(
                "❌ Ошибка авторизации: неверный код\n\n"
                "Возможные причины:\n"
                "• Код уже использован\n"
                "• Код устарел (действует 10 минут)\n"
                "• Неправильно скопирован код\n\n"
                "🔄 Получите новый код авторизации в разделе '🔗 Интеграции'"
            )
        elif "access_denied" in error_message.lower():
            await message.answer(
                "❌ Доступ запрещен\n\n"
                "Возможные причины:\n"
                "• Не разрешен доступ к Google Drive\n"
                "• Не завершена авторизация в браузере\n\n"
                "🔄 Попробуйте снова в разделе '🔗 Интеграции'"
            )
        else:
            await message.answer(
                f"❌ Ошибка подключения Google Drive: {error_message}\n\n"
                "📖 Подробная инструкция: нажмите '📖 Подробная инструкция Google Drive' в разделе интеграций"
            )


@router.callback_query(F.data == "health_track_menu")
async def health_track_menu(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Выберите показатель для записи:", reply_markup=health_track_keyboard())
    await cb.answer()


class TrackFSM(StatesGroup):
    waiting_value = State()
    metric = State()


@router.callback_query(F.data.startswith("health_track:"))
async def health_track_select(cb: types.CallbackQuery, state: FSMContext) -> None:
    metric = cb.data.split(":", 1)[1]
    await state.update_data(metric=metric)
    prompt = {
        "steps": "Введите количество шагов за сегодня (число):",
        "calories": "Введите потраченные калории за сегодня (число):",
        "sleep": "Введите продолжительность сна в минутах (число):",
        "hr": "Введите пульс покоя (число):",
        "weight": "Введите вес в кг (например 82.5):",
        "bp": "Введите давление в формате систолическое/диастолическое, например 120/80:",
    }.get(metric, "Введите значение:")
    await state.set_state(TrackFSM.waiting_value)
    await cb.message.edit_text(prompt, reply_markup=back_main_menu())
    await cb.answer()


@router.message(TrackFSM.waiting_value)
async def health_track_store(message: types.Message, state: FSMContext) -> None:
    user = message.from_user
    if not user:
        return
    data = await state.get_data()
    metric = data.get("metric")
    text = (message.text or "").strip()
    steps = calories = sleep = hr = syst = diast = None
    weight = None
    try:
        if metric == "steps":
            steps = int(text)
        elif metric == "calories":
            calories = int(text)
        elif metric == "sleep":
            sleep = int(text)
        elif metric == "hr":
            hr = int(text)
        elif metric == "weight":
            weight = float(text.replace(",", "."))
        elif metric == "bp":
            s, d = text.split("/", 1)
            syst = int(s.strip()); diast = int(d.strip())
    except Exception:
        await message.answer("Некорректный формат. Попробуйте ещё раз.")
        return

    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        rec = (
            await session.execute(
                select(HealthMetric).where(HealthMetric.user_id == db_user.id, HealthMetric.day == date.today())
            )
        ).scalar_one_or_none()
        if not rec:
            rec = HealthMetric(user_id=db_user.id, day=date.today())
            session.add(rec)
        if steps is not None: rec.steps = steps
        if calories is not None: rec.calories = calories
        if sleep is not None: rec.sleep_minutes = sleep
        if hr is not None: rec.heart_rate_resting = hr
        if weight is not None: rec.weight_kg = weight
        if syst is not None: rec.systolic = syst
        if diast is not None: rec.diastolic = diast
    await state.clear()
    await message.answer("Записано ✅", reply_markup=back_main_menu())


class GoalFSM(StatesGroup):
    waiting_metric = State()
    waiting_target = State()


@router.callback_query(F.data == "health_goals")
async def health_goals_start(cb: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GoalFSM.waiting_metric)
    await cb.message.edit_text(
        "Укажите цель. Пример: steps 8000 ИЛИ sleep 420",
        reply_markup=back_main_menu(),
    )
    await cb.answer()


@router.message(GoalFSM.waiting_metric)
async def health_goals_set(message: types.Message, state: FSMContext) -> None:
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").lower().split()
    if len(payload) < 2:
        await message.answer("Пример: steps 8000")
        return
    metric, target_str = payload[0], payload[1]
    try:
        target = float(target_str)
    except Exception:
        await message.answer("Числовое значение цели ожидалось после метрики.")
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        session.add(HealthGoal(user_id=db_user.id, metric=metric, target_value=target, period="daily"))
    await state.clear()
    await message.answer("Цель сохранена ✅", reply_markup=back_main_menu())


@router.callback_query(F.data == "health_analytics")
async def health_analytics(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer(); return
    await cb.answer("Генерирую аналитику...", show_alert=False)
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        metrics = (
            await session.execute(
                select(HealthMetric).where(HealthMetric.user_id == db_user.id).order_by(desc(HealthMetric.day)).limit(30)
            )
        ).scalars().all()
    if not metrics:
        await cb.message.edit_text("Данных пока нет. Сначала внесите показатели в Трекинге.", reply_markup=health_menu())
        return
    # Подготовка контекста и запрос к ИИ
    context_lines = []
    for m in metrics:
        context_lines.append(
            f"{m.day}: steps={m.steps}, cal={m.calories}, sleep={m.sleep_minutes}, hr={m.heart_rate_resting}, weight={m.weight_kg}, bp={m.systolic}/{m.diastolic}"
        )
    context = "\n".join(context_lines)
    system = (
        "Ты ментор-коуч для гладиатора. Проанализируй показатели здоровья (шаги, калории, сон, пульс, вес, давление) за 2-4 недели,"
        " отметь тенденции, риски и дай практические рекомендации: что усилить, что скорректировать. Кратко и по делу, 5-7 пунктов."
    )
    try:
        text = await deepseek_complete(
            prompt=f"Показатели за последние дни:\n{context}\n\nДай выводы и рекомендации.",
            system=system,
            max_tokens=700,
        )
    except Exception as e:
        await cb.message.edit_text(f"Не удалось сгенерировать аналитику: {e}")
        return
    # Отправляем двумя сообщениями
    await cb.message.edit_text("📊 Аналитика здоровья:", reply_markup=back_main_menu(), parse_mode=None)
    parts = _split_into_two_messages(text)
    if parts:
        await cb.message.answer(parts[0], parse_mode=None)
    if len(parts) > 1:
        await cb.message.answer(parts[1], parse_mode=None)


class RemindFSM(StatesGroup):
    waiting_time = State()


@router.callback_query(F.data == "health_reminders")
async def health_reminders(cb: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RemindFSM.waiting_time)
    await cb.message.edit_text(
        "Установите ежедневное время напоминания для записи показателей (HH:MM), например 21:00:",
        reply_markup=back_main_menu(),
    )
    await cb.answer()


@router.message(RemindFSM.waiting_time)
async def health_reminders_set(message: types.Message, state: FSMContext) -> None:
    user = message.from_user
    if not user:
        return
    t = (message.text or "").strip()
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        rec = (
            await session.execute(select(HealthDailyReminder).where(HealthDailyReminder.user_id == db_user.id))
        ).scalar_one_or_none()
        if not rec:
            rec = HealthDailyReminder(user_id=db_user.id)
            session.add(rec)
        rec.time_str = t
        rec.is_active = True
    await state.clear()
    await message.answer(f"Напоминание установлено на {t} ✅", reply_markup=back_main_menu())


@router.callback_query(F.data == "health_integrations")
async def health_integrations(cb: types.CallbackQuery) -> None:
    from app.services.google_fit import GoogleFitService
    from app.services.google_drive import GoogleDriveService
    
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Проверяем, есть ли уже подключенные интеграции
        google_token = (
            await session.execute(
                select(GoogleFitToken).where(GoogleFitToken.user_id == db_user.id)
            )
        ).scalar_one_or_none()
        
        if google_token:
            # Уже подключен - показываем опции в зависимости от типа
            if google_token.integration_type == "google_drive":
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🔄 Синхронизировать с Google Drive", callback_data="google_drive_sync"),
                            InlineKeyboardButton(text="❌ Отключить Google Drive", callback_data="google_drive_disconnect"),
                            InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")
                        ],
                    ]
                )
                text = "Google Drive подключен! ✅\n\nДанные читаются из файлов Health Sync на Google Drive.\n\nВыберите действие:"
            else:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🔄 Синхронизировать с Google Fit", callback_data="google_fit_sync"),
                            InlineKeyboardButton(text="❌ Отключить Google Fit", callback_data="google_fit_disconnect"),
                            InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")
                        ],
                    ]
                )
                text = "Google Fit подключен! ✅\n\nВыберите действие:"
        else:
            # Не подключен - предлагаем выбрать тип интеграции
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔗 Google Fit (прямая интеграция)", callback_data="setup_google_fit"),
                        InlineKeyboardButton(text="📁 Google Drive (через Health Sync)", callback_data="setup_google_drive"),
                        InlineKeyboardButton(text="📖 Подробная инструкция Google Drive", callback_data="google_drive_instructions")
                    ],
                    [
                        InlineKeyboardButton(text="❓ Частые вопросы", callback_data="google_drive_faq"),
                        InlineKeyboardButton(text="ℹ️ Общая справка", callback_data="google_integration_help"),
                        InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")
                    ],
                ]
            )
            text = (
                "Интеграции:\n\n"
                "🔗 **Google Fit**: прямая интеграция с API\n"
                "📁 **Google Drive**: чтение данных из файлов Health Sync\n"
                "📱 **Apple Health**: планируется\n\n"
                "**Рекомендуем Google Drive** - более стабильно и проще в настройке!\n\n"
                "Выберите тип интеграции или изучите инструкции:"
            )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "google_integration_help")
async def google_integration_help(cb: types.CallbackQuery) -> None:
    text = (
        "📱 **Как подключить интеграции:**\n\n"
        "🔗 **Google Fit (прямая интеграция):**\n"
        "1. Нажмите 'Google Fit (прямая интеграция)'\n"
        "2. Войдите в аккаунт Google\n"
        "3. Разрешите доступ к данным фитнеса\n"
        "4. Скопируйте код авторизации\n"
        "5. Отправьте код боту командой:\n"
        "   `/google_fit_auth КОД`\n\n"
        "📁 **Google Drive (через Health Sync):**\n"
        "1. Установите приложение Health Sync\n"
        "2. Настройте экспорт данных на Google Drive\n"
        "3. Нажмите 'Google Drive (через Health Sync)'\n"
        "4. Войдите в аккаунт Google\n"
        "5. Разрешите доступ к Google Drive\n"
        "6. Скопируйте код авторизации\n"
        "7. Отправьте код боту командой:\n"
        "   `/google_drive_auth КОД`\n\n"
        "После подключения данные будут синхронизироваться автоматически!"
    )
    await cb.message.edit_text(text, reply_markup=back_main_menu(), parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "google_drive_instructions")
async def google_drive_instructions(cb: types.CallbackQuery) -> None:
    text = (
        "📁 **Подробная инструкция по подключению Google Drive:**\n\n"
        "**Шаг 1: Установка Health Sync**\n"
        "• Скачайте [Health Sync](https://play.google.com/store/apps/details?id=com.urbandroid.healthsync) из Google Play\n"
        "• Откройте приложение и разрешите доступ к данным здоровья\n\n"
        "**Шаг 2: Настройка экспорта**\n"
        "• В Health Sync перейдите в 'Export' → 'Google Drive'\n"
        "• Нажмите 'Add Export'\n"
        "• Выберите 'Google Drive' как место назначения\n"
        "• Настройте периодичность: 'Daily' (ежедневно)\n"
        "• Выберите данные для экспорта:\n"
        "  ✅ Steps (шаги)\n"
        "  ✅ Sleep (сон)\n"
        "  ✅ Heart Rate (пульс)\n"
        "  ✅ Weight (вес)\n"
        "  ✅ Calories (калории)\n\n"
        "**Шаг 3: Подключение в боте**\n"
        "• Вернитесь в бота\n"
        "• Выберите 'Google Drive (через Health Sync)'\n"
        "• Следуйте инструкциям авторизации\n"
        "• Используйте команду `/google_drive_auth КОД`\n\n"
        "**Важно:** Убедитесь, что Health Sync успешно экспортировал хотя бы один файл на Google Drive перед подключением бота!"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📁 Подключить Google Drive", callback_data="setup_google_drive"),
                InlineKeyboardButton(text="❓ Частые вопросы", callback_data="google_drive_faq"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")
            ],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "google_drive_faq")
async def google_drive_faq(cb: types.CallbackQuery) -> None:
    text = (
        "❓ **Частые вопросы по Google Drive:**\n\n"
        "**Q: Почему бот не находит файлы?**\n"
        "A: Убедитесь, что Health Sync экспортировал данные на Google Drive. Проверьте папку 'HealthSync' в вашем Google Drive.\n\n"
        "**Q: Какие форматы файлов поддерживаются?**\n"
        "A: CSV, Excel (.xlsx, .xls), JSON. Health Sync обычно экспортирует в CSV.\n\n"
        "**Q: Как часто синхронизируются данные?**\n"
        "A: Автоматически каждые 6 часов. Также можно синхронизировать вручную.\n\n"
        "**Q: Что делать, если авторизация не работает?**\n"
        "A: Проверьте, что в Google Cloud Console включен Google Drive API и настроены правильные OAuth credentials.\n\n"
        "**Q: Можно ли использовать несколько аккаунтов?**\n"
        "A: Каждый пользователь бота может подключить только один Google Drive аккаунт.\n\n"
        "**Q: Безопасны ли мои данные?**\n"
        "A: Бот получает доступ только для чтения файлов. Данные не передаются третьим лицам."
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📁 Подключить Google Drive", callback_data="setup_google_drive"),
                InlineKeyboardButton(text="📖 Подробная инструкция", callback_data="google_drive_instructions"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")
            ],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "setup_google_fit")
async def setup_google_fit(cb: types.CallbackQuery) -> None:
    from app.services.google_fit import GoogleFitService
    
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        google_service = GoogleFitService()
        auth_url = google_service.get_authorization_url(db_user.id)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔗 Подключить Google Fit", url=auth_url),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")
                ],
            ]
        )
        text = (
            "🔗 **Подключение Google Fit:**\n\n"
            "1. Нажмите 'Подключить Google Fit'\n"
            "2. Войдите в аккаунт Google\n"
            "3. Разрешите доступ к данным фитнеса\n"
            "4. Скопируйте код авторизации\n"
            "5. Отправьте код боту командой:\n"
            "   `/google_fit_auth КОД`\n\n"
            "После подключения данные будут синхронизироваться автоматически!"
        )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "setup_google_drive")
async def setup_google_drive(cb: types.CallbackQuery) -> None:
    from app.services.google_drive import GoogleDriveService
    
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        google_service = GoogleDriveService()
        auth_url = google_service.get_authorization_url(db_user.id)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📁 Подключить Google Drive", url=auth_url),
                    InlineKeyboardButton(text="📖 Подробная инструкция", callback_data="google_drive_instructions"),
                    InlineKeyboardButton(text="❓ Частые вопросы", callback_data="google_drive_faq")
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")],
            ]
        )
        text = (
            "📁 **Подключение Google Drive:**\n\n"
            "**Перед подключением убедитесь:**\n"
            "✅ Health Sync установлен и настроен\n"
            "✅ Данные экспортируются на Google Drive\n"
            "✅ Есть хотя бы один файл с данными\n\n"
            "**Шаги подключения:**\n"
            "1. Нажмите '📁 Подключить Google Drive'\n"
            "2. Войдите в аккаунт Google\n"
            "3. Разрешите доступ к Google Drive\n"
            "4. Скопируйте код авторизации\n"
            "5. Отправьте код боту командой:\n"
            "   `/google_drive_auth КОД`\n\n"
            "**После подключения:**\n"
            "• Данные будут синхронизироваться автоматически\n"
            "• Можно синхронизировать вручную\n"
            "• Доступ к данным только для чтения"
        )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "google_fit_sync")
async def google_fit_sync(cb: types.CallbackQuery) -> None:
    from app.services.google_fit import GoogleFitService
    
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    await cb.answer("Синхронизирую данные...", show_alert=False)
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        google_token = (
            await session.execute(
                select(GoogleFitToken).where(
                    GoogleFitToken.user_id == db_user.id,
                    GoogleFitToken.integration_type == "google_fit"
                )
            )
        ).scalar_one_or_none()
        
        if not google_token:
            await cb.message.edit_text("Google Fit не подключен!", reply_markup=back_main_menu())
            return
        
        # Конвертируем токен в словарь
        credentials_dict = {
            'token': google_token.access_token,
            'refresh_token': google_token.refresh_token,
            'token_uri': google_token.token_uri,
            'client_id': google_token.client_id,
            'client_secret': google_token.client_secret,
            'scopes': google_token.scopes.split(',')
        }
        
        google_service = GoogleFitService()
        result = await google_service.sync_health_data(session, db_user.id, credentials_dict)
        
        if 'error' in result:
            await cb.message.edit_text(f"Ошибка синхронизации: {result['error']}", reply_markup=back_main_menu())
        else:
            text = "✅ Данные синхронизированы!\n\n"
            if result.get('steps'):
                text += f"🚶 Шаги: {result['steps']}\n"
            if result.get('calories'):
                text += f"🔥 Калории: {result['calories']}\n"
            if result.get('sleep_minutes'):
                text += f"😴 Сон: {result['sleep_minutes']} мин\n"
            if result.get('heart_rate'):
                text += f"❤️ Пульс: {result['heart_rate']} уд/мин\n"
            if result.get('weight'):
                text += f"⚖️ Вес: {result['weight']} кг\n"
            
            await cb.message.edit_text(text, reply_markup=back_main_menu())


@router.callback_query(F.data == "google_drive_sync")
async def google_drive_sync(cb: types.CallbackQuery) -> None:
    from app.services.google_drive import GoogleDriveService
    
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    await cb.answer("Синхронизирую данные с Google Drive...", show_alert=False)
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        google_token = (
            await session.execute(
                select(GoogleFitToken).where(
                    GoogleFitToken.user_id == db_user.id,
                    GoogleFitToken.integration_type == "google_drive"
                )
            )
        ).scalar_one_or_none()
        
        if not google_token:
            await cb.message.edit_text("Google Drive не подключен!", reply_markup=back_main_menu())
            return
        
        # Конвертируем токен в словарь
        credentials_dict = {
            'token': google_token.access_token,
            'refresh_token': google_token.refresh_token,
            'token_uri': google_token.token_uri,
            'client_id': google_token.client_id,
            'client_secret': google_token.client_secret,
            'scopes': google_token.scopes.split(',')
        }
        
        google_service = GoogleDriveService()
        result = await google_service.sync_health_data_from_drive(session, db_user.id, credentials_dict)
        
        if 'error' in result:
            await cb.message.edit_text(f"Ошибка синхронизации: {result['error']}", reply_markup=back_main_menu())
        else:
            text = "✅ Данные синхронизированы с Google Drive!\n\n"
            text += f"📁 Обработан файл: {result['file_processed']}\n\n"
            
            summary = result.get('data_summary', {})
            if summary.get('steps_entries'):
                text += f"🚶 Записей шагов: {summary['steps_entries']}\n"
            if summary.get('calories_entries'):
                text += f"🔥 Записей калорий: {summary['calories_entries']}\n"
            if summary.get('sleep_entries'):
                text += f"😴 Записей сна: {summary['sleep_entries']}\n"
            if summary.get('heart_rate_entries'):
                text += f"❤️ Записей пульса: {summary['heart_rate_entries']}\n"
            if summary.get('weight_entries'):
                text += f"⚖️ Записей веса: {summary['weight_entries']}\n"
            if summary.get('blood_pressure_entries'):
                text += f"🩸 Записей давления: {summary['blood_pressure_entries']}\n"
            
            await cb.message.edit_text(text, reply_markup=back_main_menu())


@router.callback_query(F.data == "google_fit_disconnect")
async def google_fit_disconnect(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        google_token = (
            await session.execute(
                select(GoogleFitToken).where(
                    GoogleFitToken.user_id == db_user.id,
                    GoogleFitToken.integration_type == "google_fit"
                )
            )
        ).scalar_one_or_none()
        
        if google_token:
            await session.delete(google_token)
            await session.commit()
            await cb.answer("Google Fit отключен!", show_alert=True)
        else:
            await cb.answer("Google Fit не был подключен", show_alert=True)
    
    await health_integrations(cb)


@router.callback_query(F.data == "google_drive_disconnect")
async def google_drive_disconnect(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        google_token = (
            await session.execute(
                select(GoogleFitToken).where(
                    GoogleFitToken.user_id == db_user.id,
                    GoogleFitToken.integration_type == "google_drive"
                )
            )
        ).scalar_one_or_none()
        
        if google_token:
            await session.delete(google_token)
            await session.commit()
            await cb.answer("Google Drive отключен!", show_alert=True)
        else:
            await cb.answer("Google Drive не был подключен", show_alert=True)
    
    await health_integrations(cb)


def _split_into_two_messages(text: str, max_len: int = 3800) -> list[str]:
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    paragraphs = text.split("\n\n")
    total_len = len(text)
    target = total_len // 2
    part1 = []
    len1 = 0
    for p in paragraphs:
        block = p + "\n\n"
        if len1 + len(block) <= max_len and (len1 + len(block) <= target or len1 == 0):
            part1.append(block)
            len1 += len(block)
        else:
            break
    p1 = "".join(part1).rstrip()
    rest = text[len(p1):].lstrip()
    if not p1:
        p1 = text[:max_len]
        rest = text[max_len:]
    if len(rest) <= max_len:
        return [p1, rest] if rest else [p1]
    return [p1, rest[:max_len - 1] + "…"]


