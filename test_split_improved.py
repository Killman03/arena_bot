#!/usr/bin/env python3
"""
Тест улучшенной функции разбиения текста на части для планов питания
"""

def _split_into_multiple_messages(text: str, max_len: int = 3000) -> list[str]:
    """Разбить текст на столько сообщений, сколько нужно для полного отображения.
    Специально оптимизировано для планов питания от DeepSeek.
    """
    if not text:
        return []
    
    # Принудительно разбиваем планы длиннее 1500 символов для лучшей читаемости
    force_split_threshold = 1500
    
    if len(text) <= force_split_threshold:
        print(f"DEBUG: План короче {force_split_threshold} символов, не разбиваем")
        return [text]
    
    # Для планов питания ищем логические точки разрыва
    lines = text.split('\n')
    
    # Ищем ключевые разделы плана питания
    section_indicators = [
        '📋', '🛒', '📝', '👨‍🍳', '🔥', '💵', '💰', '🍽️', '🥗', '🥩',
        'Список покупок:', 'Покупки:', 'Инструкции:', 'Рецепты:', 
        'Калории:', 'Стоимость:', 'Бюджет:', 'План на день',
        'День 1:', 'День 2:', 'День 3:', 'День 4:', 'День 5:',
        'Завтрак:', 'Обед:', 'Ужин:', 'Перекус:'
    ]
    
    print(f"DEBUG: Анализирую план питания из {len(lines)} строк")
    
    # Сначала пробуем разбить по логическим секциям
    parts = []
    current_part = []
    current_length = 0
    
    for i, line in enumerate(lines):
        line_length = len(line) + 1  # +1 для символа новой строки
        
        # Проверяем, не является ли эта строка разделителем секции
        is_section_break = any(indicator in line for indicator in section_indicators)
        
        # Если текущая часть станет слишком длинной или это разделитель секции
        if (current_length + line_length > max_len and current_part) or (is_section_break and current_part and current_length > max_len * 0.3):
            # Сохраняем текущую часть
            part_text = '\n'.join(current_part).strip()
            if part_text:
                parts.append(part_text)
                print(f"DEBUG: Добавлена часть {len(parts)} длиной {len(part_text)} символов")
            
            # Начинаем новую часть
            current_part = [line]
            current_length = line_length
        else:
            # Добавляем строку к текущей части
            current_part.append(line)
            current_length += line_length
    
    # Добавляем последнюю часть
    if current_part:
        part_text = '\n'.join(current_part).strip()
        if part_text:
            parts.append(part_text)
            print(f"DEBUG: Добавлена последняя часть {len(parts)} длиной {len(part_text)} символов")
    
    # Если логическое разбиение не сработало или дало слишком много частей, используем стандартное
    if len(parts) == 1 or len(parts) > 10:  # Максимум 10 частей для читаемости
        print(f"DEBUG: Логическое разбиение дало {len(parts)} частей, используем стандартное")
        # Если логическое разбиение дало только 1 часть, но текст длинный, 
        # принудительно разбиваем на несколько частей
        if len(parts) == 1 and len(text) > 1500:
            print(f"DEBUG: Принудительно разбиваю длинный план на несколько частей")
            return _split_into_parts_standard(text, max_len)
        return _split_into_parts_standard(text, max_len)
    
    print(f"DEBUG: Успешно разбил на {len(parts)} логических частей")
    return parts


def _split_into_parts_standard(text: str, max_len: int = 3000) -> list[str]:
    """Стандартное разбиение текста на части по длине"""
    if len(text) <= max_len:
        # Если текст не превышает max_len, но все равно длинный (>1500), 
        # принудительно разбиваем на 2 части для лучшей читаемости
        if len(text) > 1500:
            print(f"DEBUG: Текст длиной {len(text)} символов, принудительно разбиваю на 2 части")
            mid_point = len(text) // 2
            # Ищем хорошую точку разрыва около середины
            for i in range(mid_point - 100, mid_point + 100):
                if i < 0 or i >= len(text):
                    continue
                if text[i] == '\n':
                    mid_point = i + 1
                    break
                elif text[i] == ' ':
                    mid_point = i + 1
                    break
            
            part1 = text[:mid_point].strip()
            part2 = text[mid_point:].strip()
            
            if part1 and part2:
                print(f"DEBUG: Принудительное разбиение: часть 1 длиной {len(part1)}, часть 2 длиной {len(part2)}")
                return [part1, part2]
        
        return [text]
    
    # Оптимизируем размер частей для лучшей читаемости
    # Если текст очень длинный, разбиваем на более мелкие части
    optimal_part_size = min(max_len, 2500) if len(text) > 4000 else max_len
    
    parts = []
    remaining_text = text
    
    while len(remaining_text) > optimal_part_size:
        # Ищем точку разрыва по абзацам
        split_point = optimal_part_size
        
        # Пытаемся найти хорошую точку разрыва
        for i in range(optimal_part_size - 100, optimal_part_size):  # Ищем в последних 100 символах
            if i < 0:
                break
            if remaining_text[i] == '\n':
                split_point = i + 1
                break
            elif remaining_text[i] == ' ':
                split_point = i + 1
                break
        
        # Разбиваем текст
        part = remaining_text[:split_point].strip()
        parts.append(part)
        print(f"DEBUG: Стандартное разбиение: добавлена часть {len(parts)} длиной {len(part)} символов")
        
        remaining_text = remaining_text[split_point:].strip()
    
    # Добавляем оставшийся текст
    if remaining_text:
        parts.append(remaining_text)
        print(f"DEBUG: Стандартное разбиение: добавлена последняя часть длиной {len(remaining_text)} символов")
    
    return parts


def test_split_function():
    """Тестируем улучшенную функцию разбиения"""
    
    # Тест 1: Короткий текст
    print("=== Тест 1: Короткий текст ===")
    short_text = "Это короткий план питания на 3 дня."
    result = _split_into_multiple_messages(short_text)
    print(f"Результат: {len(result)} частей")
    for i, part in enumerate(result):
        print(f"Часть {i+1} ({len(part)} символов): {part[:100]}...")
    print()
    
    # Тест 2: Текст средней длины (не разбивается)
    print("=== Тест 2: Текст средней длины ===")
    medium_text = "Это план питания средней длины. " * 40  # ~1200 символов
    result = _split_into_multiple_messages(medium_text)
    print(f"Результат: {len(result)} частей")
    for i, part in enumerate(result):
        print(f"Часть {i+1} ({len(part)} символов): {part[:100]}...")
    print()
    
    # Тест 3: Текст, который должен разбиться (1500-3000 символов)
    print("=== Тест 3: Текст средней длины (должен разбиться) ===")
    medium_long_text = "Это план питания средней длины, который должен разбиться на части. " * 60  # ~2400 символов
    result = _split_into_multiple_messages(medium_long_text)
    print(f"Результат: {len(result)} частей")
    for i, part in enumerate(result):
        print(f"Часть {i+1} ({len(part)} символов): {part[:100]}...")
    print()
    
    # Тест 4: Длинный текст (должен разбиться на много частей)
    print("=== Тест 4: Длинный текст ===")
    long_text = "Это очень длинный план питания. " * 150  # ~4500 символов
    result = _split_into_multiple_messages(long_text)
    print(f"Результат: {len(result)} частей")
    for i, part in enumerate(result):
        print(f"Часть {i+1} ({len(part)} символов): {part[:100]}...")
    print()
    
    # Тест 5: Текст с логическими разделителями
    print("=== Тест 5: Текст с логическими разделителями ===")
    structured_text = """📋 Список покупок:
• Продукт 1
• Продукт 2
• Продукт 3

👨‍🍳 Инструкции:
• Шаг 1
• Шаг 2
• Шаг 3

🔥 Калории:
• День 1: 2000 ккал
• День 2: 2100 ккал
• День 3: 1900 ккал

💰 Стоимость:
• Общая: 1500 ₽
• На день: 500 ₽""" * 30  # ~3000 символов
    
    result = _split_into_multiple_messages(structured_text)
    print(f"Результат: {len(result)} частей")
    for i, part in enumerate(result):
        print(f"Часть {i+1} ({len(part)} символов): {part[:100]}...")
    print()


if __name__ == "__main__":
    test_split_function()
