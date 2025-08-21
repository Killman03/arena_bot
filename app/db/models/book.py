from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class BookStatus(str, Enum):
    want_to_read = "want_to_read"
    reading = "reading"
    completed = "completed"
    abandoned = "abandoned"


class Book(Base):
    """User books with status tracking."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    author: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[BookStatus] = mapped_column(SAEnum(BookStatus), default=BookStatus.want_to_read, index=True)
    
    # Reading progress
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    finish_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    current_page: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_pages: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    # Additional info
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1-5 stars
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    quotes: Mapped[list["BookQuote"]] = relationship("BookQuote", back_populates="book", cascade="all, delete-orphan")
    thoughts: Mapped[list["BookThought"]] = relationship("BookThought", back_populates="book", cascade="all, delete-orphan")


class BookQuote(Base):
    """Quotes from books."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    quote_text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    book: Mapped[Book] = relationship("Book", back_populates="quotes")


class BookThought(Base):
    """Personal thoughts and insights about books."""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"), index=True)
    thought_text: Mapped[str] = mapped_column(Text)
    thought_type: Mapped[str] = mapped_column(String(50), default="insight")  # insight, question, reflection, etc.
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    book: Mapped[Book] = relationship("Book", back_populates="thoughts")
