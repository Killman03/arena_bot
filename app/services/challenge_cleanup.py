from __future__ import annotations

from datetime import date
from typing import List

from aiogram import Bot
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Challenge, User


async def cleanup_expired_challenges(session: AsyncSession, bot: Bot) -> None:
    """Удаляет истекшие челленджи и уведомляет пользователей."""
    today = date.today()
    
    # Находим все истекшие челленджи
    expired_challenges = (
        await session.execute(
            select(Challenge).where(
                Challenge.end_date <= today,
                Challenge.end_date.is_not(None)
            )
        )
    ).scalars().all()
    
    if not expired_challenges:
        return
    
    # Группируем челленджи по пользователям для отправки уведомлений
    user_challenges = {}
    for challenge in expired_challenges:
        if challenge.user_id not in user_challenges:
            user_challenges[challenge.user_id] = []
        user_challenges[challenge.user_id].append(challenge)
    
    # Отправляем уведомления пользователям
    for user_id, challenges in user_challenges.items():
        try:
            # Получаем информацию о пользователе
            user = await session.get(User, user_id)
            if not user:
                continue
            
            # Формируем сообщение об истекших челленджах
            challenge_names = [ch.title for ch in challenges]
            message = (
                "⏰ <b>Время истекло!</b>\n\n"
                f"Следующие челленджи завершены:\n"
                f"{chr(10).join(f'• {name}' for name in challenge_names)}\n\n"
                "Поздравляем с завершением! 🎉\n"
                "Не забудьте создать новые цели для дальнейшего развития."
            )
            
            # Отправляем уведомление
            await bot.send_message(
                user.telegram_id,
                message,
                parse_mode="HTML"
            )
            
        except Exception as e:
            print(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
    
    # Удаляем истекшие челленджи
    await session.execute(
        delete(Challenge).where(
            Challenge.end_date <= today,
            Challenge.end_date.is_not(None)
        )
    )
    
    print(f"Удалено {len(expired_challenges)} истекших челленджей")
