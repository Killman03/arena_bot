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
        "• 📁 Импорт данных - загрузка ZIP файлов с данными\n\n"
        "**Импорт данных:**\n"
        "• 📱 Экспорт из приложений здоровья (Samsung Health, Google Fit)\n"
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
            
            # Проверяем, есть ли подключенная интеграция
            google_token = (
                await session.execute(
                    select(GoogleFitToken).where(
                        GoogleFitToken.user_id == db_user.id,
                        GoogleFitToken.integration_type == "health_connect"
                    )
                )
            ).scalar_one_or_none()
            
            if not google_token:
                await message.answer(
                    "❌ Health Connect не подключен!\n\n"
                    "Сначала подключите Health Connect командой:\n"
                    "`/health_connect_auth КОД`\n\n"
                    "Или через меню: Здоровье → 🔗 Интеграции → 📱 Health Connect"
                )
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
            
            # Синхронизируем данные
            health_service = HealthConnectService()
            result = await health_service.sync_health_data(session, db_user.id, credentials_dict)
            
            if 'error' in result:
                await message.answer(f"❌ Ошибка синхронизации: {result['error']}")
            else:
                text = "✅ Данные синхронизированы с Health Connect!\n\n"
                text += f"📱 Источник: Health Connect\n\n"
                
                summary = result.get('data_summary', {})
                if summary.get('steps'):
                    text += f"🚶 Шаги: {summary['steps']}\n"
                if summary.get('calories'):
                    text += f"🔥 Калории: {summary['calories']}\n"
                if summary.get('sleep_minutes'):
                    text += f"😴 Сон: {summary['sleep_minutes']} мин\n"
                if summary.get('heart_rate'):
                    text += f"❤️ Пульс: {summary['heart_rate']} уд/мин\n"
                if summary.get('weight_kg'):
                    text += f"⚖️ Вес: {summary['weight_kg']} кг\n"
                if summary.get('systolic') and summary.get('diastolic'):
                    text += f"🩸 Давление: {summary['systolic']}/{summary['diastolic']}\n"
                
                await message.answer(text)
                
    except Exception as e:
        await message.answer(f"❌ Ошибка синхронизации: {str(e)}")


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
            "Получите код, нажав 'Health Connect' в разделе Здоровье → Интеграции\n\n"
            "📱 **Health Connect** - новая платформа Google для Android 14+\n"
            "• Объединяет данные из разных приложений\n"
            "• Более стабильно чем Google Fit\n"
            "• Лучшая безопасность и приватность"
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
            
            # Сохраняем токены в базу
            google_token = GoogleFitToken(
                user_id=db_user.id,
                integration_type="health_connect",
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
                "✅ Health Connect успешно подключен!\n\n"
                "📱 **Health Connect** - новая платформа Google\n\n"
                "Теперь вы можете:\n"
                "• Синхронизировать данные из Health Connect\n"
                "• Получать данные из разных приложений (Fitbit, Samsung Health и др.)\n"
                "• Автоматические обновления каждые 6 часов\n"
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
        else:
            await message.answer(f"❌ Ошибка подключения Health Connect: {str(e)}")


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
    """Меню интеграций здоровья - теперь только простой импорт ZIP файлов."""
    text = (
        "📁 **Импорт данных здоровья**\n\n"
        "**Простой способ импорта данных:**\n"
        "• 📱 Экспортируйте данные из приложения здоровья\n"
        "• 📦 Получите ZIP файл с данными\n"
        "• 📤 Загрузите ZIP в бота\n"
        "• ✅ Данные автоматически импортируются\n\n"
        "**Поддерживаемые приложения:**\n"
        "• Samsung Health\n"
        "• Google Fit\n"
        "• Apple Health\n"
        "• Fitbit\n"
        "• И другие\n\n"
        "**Преимущества:**\n"
        "• 🚀 Быстро и просто\n"
        "• 🔒 Безопасно (файлы удаляются)\n"
        "• 📊 Автоматическое распознавание данных\n"
        "• 💾 Полный контроль над данными\n\n"
        "Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📁 Импортировать ZIP", callback_data="start_import"),
                InlineKeyboardButton(text="📚 Справка по импорту", callback_data="health_import_help")
            ],
            [
                InlineKeyboardButton(text="📊 Просмотр данных", callback_data="health_analytics"),
                InlineKeyboardButton(text="🎯 Установить цели", callback_data="health_goals")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_health")],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "google_integration_help")
async def google_integration_help(cb: types.CallbackQuery) -> None:
    text = (
        "📱 **Как подключить интеграции:**\n\n"
        "📱 **Health Connect (Android 14+):**\n"
        "1. Нажмите '📱 Health Connect (Android 14+)'\n"
        "2. Войдите в аккаунт Google\n"
        "3. Разрешите доступ к данным здоровья\n"
        "4. Скопируйте код авторизации\n"
        "5. Отправьте код боту командой:\n"
        "   `/health_connect_auth КОД`\n\n"
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
        "**Рекомендации:**\n"
        "• **Health Connect** - для Android 14+ (лучший выбор)\n"
        "• **Google Drive** - для всех устройств (стабильно)\n"
        "• **Google Fit** - для прямой интеграции\n\n"
        "После подключения данные будут синхронизироваться автоматически!"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔧 Настройка Google Cloud", callback_data="google_cloud_setup"),
                InlineKeyboardButton(text="❓ Частые вопросы", callback_data="google_integration_faq")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
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


@router.callback_query(F.data == "health_connect_instructions")
async def health_connect_instructions(cb: types.CallbackQuery) -> None:
    text = (
        "📱 **Подробная инструкция по подключению Health Connect:**\n\n"
        "**Что такое Health Connect?**\n"
        "Health Connect - это новая платформа Google для Android 14+, которая объединяет данные здоровья из разных приложений в одном месте.\n\n"
        "**Требования:**\n"
        "• Android 14 или новее\n"
        "• Google Play Services\n"
        "• Приложения, поддерживающие Health Connect\n\n"
        "**Шаг 1: Проверка совместимости**\n"
        "• Откройте Настройки → Здоровье\n"
        "• Если видите Health Connect - ваш телефон поддерживает\n"
        "• Если нет - используйте Google Fit или Google Drive\n\n"
        "**Шаг 2: Настройка Health Connect**\n"
        "• Откройте Health Connect в настройках\n"
        "• Разрешите доступ к данным здоровья\n"
        "• Подключите нужные приложения (Fitbit, Samsung Health и др.)\n\n"
        "**Шаг 3: Подключение в боте**\n"
        "• Вернитесь в бота\n"
        "• Выберите '📱 Health Connect (Android 14+)'\n"
        "• Следуйте инструкциям авторизации\n"
        "• Используйте команду `/health_connect_auth КОД`\n\n"
        "**Поддерживаемые приложения:**\n"
        "• Fitbit, Samsung Health, MyFitnessPal\n"
        "• Strava, Nike Run Club, Garmin Connect\n"
        "• Google Fit, Apple Health (через сторонние приложения)\n\n"
        "**Важно:** Убедитесь, что Health Connect настроен и содержит данные перед подключением бота!"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 Подключить Health Connect", callback_data="setup_health_connect"),
                InlineKeyboardButton(text="❓ Частые вопросы", callback_data="health_connect_faq"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")
            ],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "health_connect_faq")
async def health_connect_faq(cb: types.CallbackQuery) -> None:
    text = (
        "❓ **Частые вопросы по Health Connect:**\n\n"
        "**Q: Почему не вижу Health Connect в настройках?**\n"
        "A: Health Connect доступен только на Android 14+. На более старых версиях используйте Google Fit или Google Drive.\n\n"
        "**Q: Какие приложения поддерживают Health Connect?**\n"
        "A: Fitbit, Samsung Health, MyFitnessPal, Strava, Nike Run Club, Garmin Connect и многие другие.\n\n"
        "**Q: Как часто синхронизируются данные?**\n"
        "A: Автоматически каждые 6 часов. Также можно синхронизировать вручную.\n\n"
        "**Q: Что делать, если авторизация не работает?**\n"
        "A: Проверьте, что в Google Cloud Console включен Google Fit API и настроены правильные OAuth credentials.\n\n"
        "**Q: Можно ли использовать несколько аккаунтов?**\n"
        "A: Каждый пользователь бота может подключить только один Health Connect аккаунт.\n\n"
        "**Q: Безопасны ли мои данные?**\n"
        "A: Бот получает доступ только для чтения данных. Данные не передаются третьим лицам.\n\n"
        "**Q: В чем отличие от Google Fit?**\n"
        "A: Health Connect - новая платформа с лучшей безопасностью, стабильностью и поддержкой большего количества приложений."
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 Подключить Health Connect", callback_data="setup_health_connect"),
                InlineKeyboardButton(text="📖 Подробная инструкция", callback_data="health_connect_instructions"),
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


@router.callback_query(F.data == "setup_health_connect")
async def setup_health_connect(cb: types.CallbackQuery) -> None:
    from app.services.health_connect import HealthConnectService
    
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        health_service = HealthConnectService()
        auth_url = health_service.get_authorization_url(db_user.id)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📱 Подключить Health Connect", url=auth_url),
                    InlineKeyboardButton(text="📖 Подробная инструкция", callback_data="health_connect_instructions")
                ],
                [
                    InlineKeyboardButton(text="❓ Частые вопросы", callback_data="health_connect_faq"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="health_integrations")
                ],
            ]
        )
        text = (
            "📱 **Подключение Health Connect:**\n\n"
            "**Health Connect** - новая платформа Google для Android 14+\n\n"
            "**Преимущества:**\n"
            "• 🔗 Объединяет данные из разных приложений\n"
            "• 📱 Работает на Android 14+\n"
            "• 🚀 Более стабильно чем Google Fit\n"
            "• 🔒 Лучшая безопасность и приватность\n\n"
            "**Поддерживаемые приложения:**\n"
            "• Fitbit, Samsung Health, MyFitnessPal\n"
            "• Strava, Nike Run Club, Garmin Connect\n"
            "• И многие другие\n\n"
            "**Шаги подключения:**\n"
            "1. Нажмите '📱 Подключить Health Connect'\n"
            "2. Войдите в аккаунт Google\n"
            "3. Разрешите доступ к данным здоровья\n"
            "4. Скопируйте код авторизации\n"
            "5. Отправьте код боту командой:\n"
            "   `/health_connect_auth КОД`\n\n"
            "**После подключения:**\n"
            "• Данные будут синхронизироваться автоматически\n"
            "• Можно синхронизировать вручную\n"
            "• Доступ к данным только для чтения"
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


@router.callback_query(F.data == "health_connect_sync")
async def health_connect_sync(cb: types.CallbackQuery) -> None:
    from app.services.health_connect import HealthConnectService
    
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    await cb.answer("Синхронизирую данные с Health Connect...", show_alert=False)
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        google_token = (
            await session.execute(
                select(GoogleFitToken).where(
                    GoogleFitToken.user_id == db_user.id,
                    GoogleFitToken.integration_type == "health_connect"
                )
            )
        ).scalar_one_or_none()
        
        if not google_token:
            await cb.message.edit_text("Health Connect не подключен!", reply_markup=back_main_menu())
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
        
        health_service = HealthConnectService()
        result = await health_service.sync_health_data(session, db_user.id, credentials_dict)
        
        if 'error' in result:
            await cb.message.edit_text(f"Ошибка синхронизации: {result['error']}", reply_markup=back_main_menu())
        else:
            text = "✅ Данные синхронизированы с Health Connect!\n\n"
            text += f"📱 Источник: Health Connect\n\n"
            
            summary = result.get('data_summary', {})
            if summary.get('steps'):
                text += f"🚶 Шаги: {summary['steps']}\n"
            if summary.get('calories'):
                text += f"🔥 Калории: {summary['calories']}\n"
            if summary.get('sleep_minutes'):
                text += f"😴 Сон: {summary['sleep_minutes']} мин\n"
            if summary.get('heart_rate'):
                text += f"❤️ Пульс: {summary['heart_rate']} уд/мин\n"
            if summary.get('weight_kg'):
                text += f"⚖️ Вес: {summary['weight_kg']} кг\n"
            if summary.get('systolic') and summary.get('diastolic'):
                text += f"🩸 Давление: {summary['systolic']}/{summary['diastolic']}\n"
            
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


@router.callback_query(F.data == "health_connect_disconnect")
async def health_connect_disconnect(cb: types.CallbackQuery) -> None:
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
                    GoogleFitToken.integration_type == "health_connect"
                )
            )
        ).scalar_one_or_none()
        
        if google_token:
            await session.delete(google_token)
            await session.commit()
            await cb.answer("Health Connect отключен!", show_alert=True)
        else:
            await cb.answer("Health Connect не был подключен", show_alert=True)
    
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


@router.callback_query(F.data == "google_cloud_setup")
async def google_cloud_setup(cb: types.CallbackQuery) -> None:
    """Инструкция по настройке Google Cloud Console."""
    text = (
        "🔧 **Настройка Google Cloud Console для интеграций:**\n\n"
        "**Шаг 1: Создание проекта**\n"
        "1. Откройте [Google Cloud Console](https://console.cloud.google.com/)\n"
        "2. Создайте новый проект или выберите существующий\n"
        "3. Запомните **Project ID**\n\n"
        "**Шаг 2: Включение API**\n"
        "В разделе **'APIs & Services' → 'Library'** включите:\n"
        "• ✅ **Google Fit API** (для Health Connect и Google Fit)\n"
        "• ✅ **Google Drive API** (для Google Drive интеграции)\n"
        "• ✅ **Google+ API** (если требуется)\n\n"
        "**Шаг 3: Создание OAuth 2.0 credentials**\n"
        "1. Перейдите в **'APIs & Services' → 'Credentials'**\n"
        "2. Нажмите **'Create Credentials' → 'OAuth 2.0 Client IDs'**\n"
        "3. Выберите тип: **'Web application'**\n"
        "4. Добавьте **Authorized redirect URIs**:\n"
        "   ```\n"
        "   http://localhost:8000/auth/google/callback\n"
        "   https://yourdomain.com/auth/google/callback  # если есть домен\n"
        "   ```\n"
        "5. Сохраните **Client ID** и **Client Secret**\n\n"
        "**Шаг 4: Настройка переменных окружения**\n"
        "В файле `.env` заполните:\n"
        "```env\n"
        "GOOGLE_CLIENT_ID=your_actual_client_id_here\n"
        "GOOGLE_CLIENT_SECRET=your_actual_client_secret_here\n"
        "GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback\n"
        "```\n\n"
        "**Шаг 5: Перезапуск бота**\n"
        "После изменения `.env` **обязательно** перезапустите бота!\n\n"
        "**🔗 Полезные ссылки:**\n"
        "• [Google Cloud Console](https://console.cloud.google.com/)\n"
        "• [APIs & Services → Library](https://console.cloud.google.com/apis/library)\n"
        "• [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)\n\n"
        "**⚠️ Важно:** Не забудьте перезапустить бота после настройки!"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔧 Проверить конфигурацию", callback_data="check_google_config"),
                InlineKeyboardButton(text="❓ Частые ошибки", callback_data="google_cloud_errors")
            ],
            [
                InlineKeyboardButton(text="📱 Health Connect", callback_data="setup_health_connect"),
                InlineKeyboardButton(text="🔗 Google Fit", callback_data="setup_google_fit")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="google_integration_help")],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "google_cloud_errors")
async def google_cloud_errors(cb: types.CallbackQuery) -> None:
    """Частые ошибки при настройке Google Cloud Console."""
    text = (
        "❌ **Частые ошибки при настройке Google Cloud Console:**\n\n"
        "**🚨 Ошибка 1: 'Доступ заблокирован'**\n"
        "**Причина:** Не настроены Google credentials\n"
        "**Решение:**\n"
        "1. Проверьте файл `.env`\n"
        "2. Убедитесь, что GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET заполнены\n"
        "3. Перезапустите бота\n\n"
        "**🚨 Ошибка 2: 'Invalid client_id'**\n"
        "**Причина:** Неправильный Client ID\n"
        "**Решение:**\n"
        "1. Скопируйте Client ID из Google Cloud Console полностью\n"
        "2. Проверьте, что нет лишних пробелов\n"
        "3. Перезапустите бота\n\n"
        "**🚨 Ошибка 3: 'Redirect URI mismatch'**\n"
        "**Причина:** Неверный redirect URI\n"
        "**Решение:**\n"
        "1. В Google Cloud Console добавьте: `http://localhost:8000/auth/google/callback`\n"
        "2. Убедитесь, что URI в `.env` совпадает\n"
        "3. Перезапустите бота\n\n"
        "**🚨 Ошибка 4: 'API not enabled'**\n"
        "**Причина:** API не включены\n"
        "**Решение:**\n"
        "1. Включите Google Fit API и Google Drive API\n"
        "2. Подождите несколько минут после включения\n"
        "3. Попробуйте снова\n\n"
        "**🔧 Диагностика:**\n"
        "• Запустите: `python check_config.py`\n"
        "• Проверьте логи бота\n"
        "• Убедитесь, что Google Cloud Console доступен\n\n"
        "**💡 Профилактика:**\n"
        "• Всегда перезапускайте бота после изменения `.env`\n"
        "• Проверяйте правильность копирования credentials\n"
        "• Используйте актуальные redirect URI"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔧 Настройка Google Cloud", callback_data="google_cloud_setup"),
                InlineKeyboardButton(text="📋 Проверить конфигурацию", callback_data="check_google_config")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="google_cloud_setup")],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "check_google_config")
async def check_google_config(cb: types.CallbackQuery) -> None:
    """Проверка конфигурации Google credentials."""
    text = (
        "🔍 **Проверка конфигурации Google credentials:**\n\n"
        "**Для проверки конфигурации выполните:**\n\n"
        "**1. Проверка файла .env**\n"
        "```bash\n"
        "python check_config.py\n"
        "```\n\n"
        "**2. Проверка переменных окружения**\n"
        "```bash\n"
        "python -c \"from app.config import settings; print('Client ID:', settings.google_client_id); print('Client Secret:', 'SET' if settings.google_client_secret else 'NOT SET')\"\n"
        "```\n\n"
        "**3. Тест Health Connect сервиса**\n"
        "```bash\n"
        "python test_health_connect.py\n"
        "```\n\n"
        "**📋 Что должно быть в .env:**\n"
        "```env\n"
        "GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com\n"
        "GOOGLE_CLIENT_SECRET=GOCSPX-abcdefghijklmnopqrstuvwxyz\n"
        "GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback\n"
        "```\n\n"
        "**✅ Признаки правильной настройки:**\n"
        "• Client ID начинается с цифр и содержит `.apps.googleusercontent.com`\n"
        "• Client Secret начинается с `GOCSPX-`\n"
        "• Бот запускается без ошибок\n"
        "• В меню интеграций видно Health Connect\n\n"
        "**❌ Признаки неправильной настройки:**\n"
        "• Client ID = `your_google_client_id`\n"
        "• Client Secret = `your_google_client_secret`\n"
        "• Ошибка 'доступ заблокирован' при подключении\n"
        "• Бот не запускается"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔧 Настройка Google Cloud", callback_data="google_cloud_setup"),
                InlineKeyboardButton(text="❓ Частые ошибки", callback_data="google_cloud_errors")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="google_cloud_setup")],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "google_integration_faq")
async def google_integration_faq(cb: types.CallbackQuery) -> None:
    """FAQ по интеграциям Google."""
    text = (
        "❓ **Частые вопросы по интеграциям Google:**\n\n"
        "**Q: Почему не работает Health Connect?**\n"
        "A: Проверьте:\n"
        "• Android 14+ на телефоне\n"
        "• Настроен ли Google Cloud Console\n"
        "• Правильно ли заполнен .env файл\n"
        "• Перезапущен ли бот после изменений\n\n"
        "**Q: Что делать при ошибке 'доступ заблокирован'?**\n"
        "A: Это означает, что не настроены Google credentials:\n"
        "1. Настройте Google Cloud Console\n"
        "2. Заполните .env файл\n"
        "3. Перезапустите бота\n\n"
        "**Q: Как часто синхронизируются данные?**\n"
        "A: Автоматически каждые 6 часов. Также можно синхронизировать вручную.\n\n"
        "**Q: Можно ли использовать несколько аккаунтов?**\n"
        "A: Каждый пользователь бота может подключить только один аккаунт Google.\n\n"
        "**Q: Безопасны ли мои данные?**\n"
        "A: Бот получает доступ только для чтения данных. Данные не передаются третьим лицам.\n\n"
        "**Q: Что делать, если авторизация не работает?**\n"
        "A: Проверьте настройки Google Cloud Console и убедитесь, что API включены."
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔧 Настройка Google Cloud", callback_data="google_cloud_setup"),
                InlineKeyboardButton(text="📋 Проверить конфигурацию", callback_data="check_google_config")
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="google_integration_help")],
        ]
    )
    
    await cb.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await cb.answer()


@router.callback_query(F.data == "start_import")
async def start_import_from_menu(cb: types.CallbackQuery, state: FSMContext) -> None:
    """Начинает импорт из главного меню здоровья."""
    from app.handlers.zip_import import import_health_start
    await import_health_start(cb.message, state)
    await cb.answer()


@router.callback_query(F.data == "health_import_help")
async def health_import_help_from_menu(cb: types.CallbackQuery) -> None:
    """Показывает справку по импорту из главного меню."""
    from app.handlers.zip_import import health_import_help
    await health_import_help(cb.message)
    await cb.answer()


def _split_into_two_messages(text: str, max_len: int = 2000) -> list[str]:
    """Разбить текст на несколько сообщений для лучшей читаемости"""
    if not text:
        return []
    
    # Если текст короткий, не разбиваем
    if len(text) <= max_len:
        return [text]
    
    # Если текст очень длинный (>4000), разбиваем на 3 части
    if len(text) > 4000:
        print(f"DEBUG: Текст очень длинный ({len(text)} символов), разбиваю на 3 части")
        part_size = len(text) // 3
        
        # Ищем хорошие точки разрыва
        split1 = part_size
        split2 = part_size * 2
        
        # Ищем ближайшие переносы строк или пробелы
        for i in range(part_size - 100, part_size + 100):
            if i < 0 or i >= len(text):
                continue
            if text[i] == '\n' or text[i] == ' ':
                split1 = i + 1
                break
        
        for i in range(part_size * 2 - 100, part_size * 2 + 100):
            if i < 0 or i >= len(text):
                continue
            if text[i] == '\n' or text[i] == ' ':
                split2 = i + 1
                break
        
        part1 = text[:split1].strip()
        part2 = text[split1:split2].strip()
        part3 = text[split2:].strip()
        
        if part1 and part2 and part3:
            return [part1, part2, part3]
        elif part1 and part2:
            return [part1, part2]
        else:
            return [text]
    
    # Стандартное разбиение на 2 части
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
    
    # Если вторая часть слишком длинная, разбиваем её тоже
    if len(rest) > max_len:
        print(f"DEBUG: Вторая часть слишком длинная ({len(rest)} символов), разбиваю её")
        mid_point = len(rest) // 2
        for i in range(mid_point - 100, mid_point + 100):
            if i < 0 or i >= len(rest):
                continue
            if rest[i] == '\n' or rest[i] == ' ':
                mid_point = i + 1
                break
        
        part2 = rest[:mid_point].strip()
        part3 = rest[mid_point:].strip()
        
        if part2 and part3:
            return [p1, part2, part3]
        else:
            return [p1, rest[:max_len - 1] + "…"]
    
    return [p1, rest]


