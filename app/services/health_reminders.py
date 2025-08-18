from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.models import User, HealthMetric, HealthReminder
from app.config import settings


async def send_health_daily_prompt(bot: Bot, session: AsyncSession) -> None:
    """Send daily health prompts to users"""
    try:
        users = (await session.execute(select(User))).scalars().all()
        
        for user in users:
            try:
                user_tz = user.timezone or settings.default_timezone
                user_now = datetime.now(ZoneInfo(user_tz))
                
                # Send health prompt at 9 AM user time
                if user_now.hour == 9 and user_now.minute == 0:
                    # Check if user has recent health metrics
                    yesterday = user_now - timedelta(days=1)
                    recent_metrics = await session.execute(
                        select(HealthMetric).where(
                            HealthMetric.user_id == user.id,
                            HealthMetric.recorded_at >= yesterday
                        )
                    )
                    recent_metrics = recent_metrics.scalars().all()
                    
                    if not recent_metrics:
                        await bot.send_message(
                            user.telegram_id,
                            "🏥 Доброе утро! Не забудьте записать показатели здоровья за сегодня.\n"
                            "Используйте /health_metric для добавления метрик."
                        )
                    else:
                        await bot.send_message(
                            user.telegram_id,
                            "🏥 Доброе утро! Отлично, что вы следите за здоровьем! 💪"
                        )
            except Exception as e:
                print(f"Error sending health prompt to user {user.id}: {e}")
                continue
    except Exception as e:
        print(f"Error in health daily prompt job: {e}")


async def sync_google_fit_data(bot: Bot, session: AsyncSession) -> None:
    """Sync Google Fit data for users with connected accounts"""
    try:
        # This would integrate with Google Fit API
        # For now, just log that the job ran
        print("Google Fit sync job executed - would sync data if API was configured")
        
        # In a real implementation, you would:
        # 1. Get users with Google Fit tokens
        # 2. Use Google Fit API to fetch data
        # 3. Store the data in HealthMetric table
        # 4. Send notifications about new data
        
    except Exception as e:
        print(f"Error in Google Fit sync job: {e}")


async def send_health_reminder_notifications(bot: Bot, session: AsyncSession) -> None:
    """Send notifications for scheduled health reminders"""
    try:
        now = datetime.now()
        
        # Get active health reminders
        reminders = await session.execute(
            select(HealthReminder).where(
                HealthReminder.is_active == True,
                HealthReminder.reminder_time <= now
            )
        )
        reminders = reminders.scalars().all()
        
        for reminder in reminders:
            try:
                # Get user for this reminder
                user = await session.execute(
                    select(User).where(User.id == reminder.user_id)
                )
                user = user.scalar_one_or_none()
                
                if user:
                    await bot.send_message(
                        user.telegram_id,
                        f"🏥 Напоминание о здоровье: {reminder.message}"
                    )
                    
                    # If it's a recurring reminder, update the next reminder time
                    if reminder.is_recurring and reminder.recurrence_pattern:
                        if reminder.recurrence_pattern == "daily":
                            reminder.reminder_time = reminder.reminder_time + timedelta(days=1)
                        elif reminder.recurrence_pattern == "weekly":
                            reminder.reminder_time = reminder.reminder_time + timedelta(weeks=1)
                        elif reminder.recurrence_pattern == "monthly":
                            reminder.reminder_time = reminder.reminder_time + timedelta(days=30)
                    
                    await session.commit()
                    
            except Exception as e:
                print(f"Error sending health reminder {reminder.id}: {e}")
                continue
                
    except Exception as e:
        print(f"Error in health reminder notifications job: {e}")
