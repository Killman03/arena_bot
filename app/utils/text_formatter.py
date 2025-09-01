from __future__ import annotations

import re
from typing import List


def format_ai_response(text: str) -> str:
    """
    Форматирует ответ от ИИ, заменяя неправильные символы на корректный Markdown
    """
    # Заменяем *текст* на **текст** для жирного шрифта
    text = re.sub(r'\*([^*]+)\*', r'**\1**', text)
    
    # Заменяем _текст_ на *текст* для курсива (если не в середине слова)
    text = re.sub(r'\b_([^_]+)_\b', r'*\1*', text)
    
    # Заменяем `текст` на `текст` для моноширинного шрифта (уже корректно)
    
    # Заменяем \текст\ на `текст` для моноширинного шрифта
    text = re.sub(r'\\([^\\]+)\\', r'`\1`', text)
    
    return text


def split_long_message(text: str, max_length: int = 4096) -> List[str]:
    """
    Разбивает длинное сообщение на части, не превышающие максимальную длину
    
    Args:
        text: Текст для разбиения
        max_length: Максимальная длина одной части (по умолчанию 4096 для Telegram)
    
    Returns:
        Список частей текста
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    # Разбиваем по предложениям
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        # Если добавление предложения превысит лимит
        if len(current_part) + len(sentence) + 1 > max_length:
            if current_part:
                parts.append(current_part.strip())
                current_part = sentence
            else:
                # Если одно предложение слишком длинное, разбиваем по словам
                words = sentence.split()
                for word in words:
                    if len(current_part) + len(word) + 1 > max_length:
                        if current_part:
                            parts.append(current_part.strip())
                            current_part = word
                        else:
                            # Если одно слово слишком длинное, разбиваем по символам
                            if len(word) > max_length:
                                for i in range(0, len(word), max_length):
                                    parts.append(word[i:i + max_length])
                            else:
                                current_part = word
                    else:
                        current_part += " " + word if current_part else word
        else:
            current_part += " " + sentence if current_part else sentence
    
    if current_part.strip():
        parts.append(current_part.strip())
    
    return parts


def format_and_split_ai_response(text: str, max_length: int = 4096) -> List[str]:
    """
    Форматирует ответ от ИИ и разбивает на части, если необходимо
    
    Args:
        text: Исходный текст от ИИ
        max_length: Максимальная длина одной части
    
    Returns:
        Список отформатированных частей текста
    """
    formatted_text = format_ai_response(text)
    return split_long_message(formatted_text, max_length)
