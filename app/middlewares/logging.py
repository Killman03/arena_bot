from __future__ import annotations

from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import User, Interaction


class InteractionLoggingMiddleware(BaseMiddleware):
    """Middleware to persist all incoming messages as interactions."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.from_user:
            async with session_scope() as session:
                db_user = (
                    await session.execute(select(User).where(User.telegram_id == event.from_user.id))
                ).scalar_one_or_none()
                if db_user is None:
                    db_user = User(
                        telegram_id=event.from_user.id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name,
                    )
                    session.add(db_user)
                    await session.flush()
                session.add(
                    Interaction(
                        user_id=db_user.id,
                        message_text=event.text or "",
                        command=event.text.split()[0] if event.text and event.text.startswith("/") else None,
                        meta={
                            "chat_id": event.chat.id,
                            "message_id": event.message_id,
                        },
                    )
                )
        return await handler(event, data)


