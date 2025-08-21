from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class BookBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    author: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = None
    genre: Optional[str] = Field(None, max_length=100)
    total_pages: Optional[int] = Field(None, ge=1)


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    author: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    finish_date: Optional[date] = None
    current_page: Optional[int] = Field(None, ge=0)
    total_pages: Optional[int] = Field(None, ge=1)
    genre: Optional[str] = Field(None, max_length=100)
    rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None


class BookResponse(BookBase):
    id: int
    user_id: int
    status: str
    start_date: Optional[date] = None
    finish_date: Optional[date] = None
    current_page: Optional[int] = None
    total_pages: Optional[int] = None
    rating: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BookQuoteBase(BaseModel):
    quote_text: str = Field(..., min_length=1)
    page_number: Optional[int] = Field(None, ge=1)
    context: Optional[str] = None


class BookQuoteCreate(BookQuoteBase):
    book_id: int


class BookQuoteResponse(BookQuoteBase):
    id: int
    book_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BookThoughtBase(BaseModel):
    thought_text: str = Field(..., min_length=1)
    thought_type: str = Field(default="insight", max_length=50)


class BookThoughtCreate(BookThoughtBase):
    book_id: int


class BookThoughtResponse(BookThoughtBase):
    id: int
    book_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BookWithContent(BookResponse):
    quotes: list[BookQuoteResponse] = []
    thoughts: list[BookThoughtResponse] = []
