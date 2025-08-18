from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


class Recipe(Base):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    ingredients: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(256), nullable=True)


class MealPlan(Base):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    date: Mapped[date]
    type: Mapped[MealType] = mapped_column(SAEnum(MealType), index=True)
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipe.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    calories: Mapped[int | None] = mapped_column(nullable=True)


class NutritionLog(Base):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    date: Mapped[date]
    score: Mapped[int]
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class CookingSession(Base):
    """Сессия готовки на несколько дней."""
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    cooking_date: Mapped[date] = mapped_column()
    target_days: Mapped[int] = mapped_column(default=3)  # На сколько дней готовим
    calories_per_day: Mapped[int | None] = mapped_column(nullable=True)
    shopping_list: Mapped[str | None] = mapped_column(Text, nullable=True)  # Список продуктов от ИИ
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)  # Инструкции от ИИ
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # Заметки пользователя
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class NutritionReminder(Base):
    """Настройки напоминаний о готовке."""
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True, unique=True)
    cooking_days: Mapped[str] = mapped_column(String(50), default="wednesday,sunday")  # Дни готовки
    cooking_time: Mapped[str] = mapped_column(String(10), default="18:00")  # Время готовки
    reminder_time: Mapped[str] = mapped_column(String(10), default="17:00")  # Время напоминания
    shopping_reminder_time: Mapped[str] = mapped_column(String(10), default="16:00")  # Время напоминания о покупках
    is_active: Mapped[bool] = mapped_column(default=True)
    target_calories: Mapped[int | None] = mapped_column(nullable=True)
    body_goal: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "cut", "bulk", "maintain"
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)






