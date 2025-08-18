from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.db.models import User
from app.config import settings


async def send_cooking_day_reminders(bot: Bot, session: AsyncSession) -> None:
    """Send cooking day reminders to users"""
    try:
        # Get users who have cooking day preferences
        users = (await session.execute(select(User))).scalars().all()
        
        for user in users:
            try:
                # Check if it's cooking day for this user
                user_tz = user.timezone or settings.default_timezone
                user_now = datetime.now(ZoneInfo(user_tz))
                
                # Simple logic: remind on specific days (e.g., Sunday for meal prep)
                if user_now.weekday() == 6:  # Sunday
                    await bot.send_message(
                        user.telegram_id,
                        "🍳 Воскресенье - день приготовления еды! Не забудьте спланировать меню на неделю."
                    )
            except Exception as e:
                # Log error but continue with other users
                print(f"Error sending cooking reminder to user {user.id}: {e}")
                continue
    except Exception as e:
        print(f"Error in cooking reminders job: {e}")


async def send_shopping_day_reminders(bot: Bot, session: AsyncSession) -> None:
    """Send shopping day reminders to users"""
    try:
        # Get users who have shopping day preferences
        users = (await session.execute(select(User))).scalars().all()
        
        for user in users:
            try:
                # Check if it's shopping day for this user
                user_tz = user.timezone or settings.default_timezone
                user_now = datetime.now(ZoneInfo(user_tz))
                
                # Simple logic: remind on specific days (e.g., Saturday for shopping)
                if user_now.weekday() == 5:  # Saturday
                    await bot.send_message(
                        user.telegram_id,
                        "🛒 Суббота - день покупок! Составьте список необходимых продуктов."
                    )
            except Exception as e:
                # Log error but continue with other users
                print(f"Error sending shopping reminder to user {user.id}: {e}")
                continue
    except Exception as e:
        print(f"Error in shopping reminders job: {e}")
