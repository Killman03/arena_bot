from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, HealthDailyReminder, GoogleFitToken


async def send_health_daily_prompt(bot: Bot, session: AsyncSession) -> None:
    now_utc = datetime.now(timezone.utc)
    users = (await session.execute(select(User))).scalars().all()
    for u in users:
        tz = u.timezone or settings.default_timezone
        try:
            user_now = now_utc.astimezone(ZoneInfo(tz))
        except Exception:
            user_now = now_utc.astimezone(ZoneInfo(settings.default_timezone))
        rec = (
            await session.execute(select(HealthDailyReminder).where(HealthDailyReminder.user_id == u.id))
        ).scalar_one_or_none()
        if not rec or not rec.is_active:
            continue
        if user_now.strftime("%H:%M") != rec.time_str:
            continue
        try:
            await bot.send_message(
                u.telegram_id,
                "🔔 Пора записать показатели здоровья: шаги, сон, вес и др. Зайдите в '🩺 Здоровье' → '📈 Трекинг показателей'.",
            )
        except Exception:
            continue


async def sync_google_fit_data(bot: Bot, session: AsyncSession) -> None:
    """Автоматическая синхронизация данных Google Fit и Google Drive для всех подключенных пользователей."""
    try:
        from app.services.google_fit import GoogleFitService
        from app.services.google_drive import GoogleDriveService
        
        # Получаем всех пользователей с подключенными интеграциями
        google_tokens = (await session.execute(select(GoogleFitToken))).scalars().all()
        
        if not google_tokens:
            return
        
        for token in google_tokens:
            try:
                # Конвертируем токен в словарь
                credentials_dict = {
                    'token': token.access_token,
                    'refresh_token': token.refresh_token,
                    'token_uri': token.token_uri,
                    'client_id': token.client_id,
                    'client_secret': token.client_secret,
                    'scopes': token.scopes.split(',')
                }
                
                # Выбираем сервис в зависимости от типа интеграции
                if token.integration_type == "google_drive":
                    google_service = GoogleDriveService()
                    result = await google_service.sync_health_data_from_drive(session, token.user_id, credentials_dict, days_back=1)
                    service_name = "Google Drive"
                else:
                    google_service = GoogleFitService()
                    result = await google_service.sync_health_data(session, token.user_id, credentials_dict, days_back=1)
                    service_name = "Google Fit"
                
                if 'error' not in result:
                    # Уведомляем пользователя об успешной синхронизации
                    user = (await session.execute(select(User).where(User.id == token.user_id))).scalar_one()
                    if user:
                        if token.integration_type == "google_drive":
                            text = f"🔄 {service_name}: данные синхронизированы\n\n"
                            text += f"📁 Обработан файл: {result.get('file_processed', 'Неизвестно')}\n\n"
                            
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
                        else:
                            text = f"🔄 {service_name}: данные синхронизированы\n\n"
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
                        
                        try:
                            await bot.send_message(user.telegram_id, text)
                        except Exception:
                            continue
                            
            except Exception as e:
                # Логируем ошибку, но продолжаем с другими пользователями
                print(f"Error syncing {token.integration_type} for user {token.user_id}: {e}")
                continue
                
    except Exception as e:
        print(f"Error in Google integration sync job: {e}")


