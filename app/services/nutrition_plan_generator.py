from __future__ import annotations

from app.services.llm import deepseek_complete


async def generate_cooking_plan(budget_info: dict = None) -> str:
    """Генерирует план готовки на 2 дня с помощью ИИ"""
    # Формируем системный промпт с учетом бюджета
    budget_context = ""
    if budget_info and budget_info["type"]:
        daily_budget = budget_info["amount"] / 30  # Примерный дневной бюджет
        budget_context = f"ВАЖНО: Учитывай бюджет питания {budget_info['description']}. Примерно {daily_budget:.0f} ₽ в день. "
        
        if daily_budget < 300:
            budget_context += "Выбирай самые экономные продукты: крупы, макароны, яйца, сезонные овощи, курица."
        elif daily_budget < 500:
            budget_context += "Используй доступные продукты: мясо курицы/свинины, рыба недорогая, овощи, фрукты по сезону."
        elif daily_budget < 700:
            budget_context += "Можешь включить качественное мясо, рыбу, разнообразные овощи и фрукты."
        else:
            budget_context += "Можешь предложить премиальные продукты, деликатесы, экзотические ингредиенты."
    
    # Добавляем информацию о целях в системный промпт
    goal_context = ""
    if budget_info and budget_info.get("body_goal"):
        goal_text = budget_info["body_goal"]
        if goal_text == "cut":
            goal_context = "ВАЖНО: Пользователь на сушке (снижение веса). Создай план с дефицитом калорий, больше белка, меньше углеводов. "
        elif goal_text == "bulk":
            goal_context = "ВАЖНО: Пользователь на массе (набор веса). Создай план с профицитом калорий, больше углеводов и белка. "
        elif goal_text == "maintain":
            goal_context = "ВАЖНО: Пользователь поддерживает вес. Создай сбалансированный план без дефицита/профицита калорий. "
    
    if budget_info and budget_info.get("target_calories"):
        goal_context += f"Целевые калории: {budget_info['target_calories']} в день. "
    
    system = (
        f"Ты нутрициолог и кулинар. {budget_context}{goal_context}"
        "Составь план готовки на 2 дня со сбалансированным полезным питанием. "
        "ОБЯЗАТЕЛЬНО включи ВСЕ разделы:\n"
        "1. 📋 Список покупок (с количеством и ценами)\n"
        "2. 👨‍🍳 Инструкции готовки по дням\n"
        "3. 🔥 Калории на день\n"
        "4. 💰 Общая стоимость\n\n"
        "Будь ДЕТАЛЬНЫМ и ПОЛНЫМ. Не обрезай ответ. "
        "Если нужно больше места - используй его. "
        "Каждый раздел должен быть информативным и полезным."
    )
    
    prompt_parts = ["Сделай список покупок и инструкции на 2 дня."]
    if budget_info and budget_info["type"]:
        prompt_parts.append(f"Бюджет: {budget_info['description']}.")
    
    # Добавляем информацию о целях пользователя
    if budget_info and budget_info.get("body_goal"):
        goal_text = budget_info["body_goal"]
        if goal_text == "cut":
            prompt_parts.append("Цель: сушка (снижение веса).")
        elif goal_text == "bulk":
            prompt_parts.append("Цель: набор массы.")
        elif goal_text == "maintain":
            prompt_parts.append("Цель: поддержание веса.")
        else:
            prompt_parts.append(f"Цель: {goal_text}.")
    
    if budget_info and budget_info.get("target_calories"):
        prompt_parts.append(f"Целевые калории: {budget_info['target_calories']} в день.")
    
    prompt_parts.append("Формат: Покупки с ценами, Инструкции, Калории/день.")
    
    prompt = " ".join(prompt_parts)
    
    try:
        print(f"DEBUG: Отправляю запрос к ИИ с prompt='{prompt[:100]}...' и system='{system[:100]}...'")
        print(f"DEBUG: Использую max_tokens=5000 для получения полного плана")
        
        # Сразу используем максимальные параметры для получения полного плана
        result = await deepseek_complete(prompt, system=system, max_tokens=5000)
        
        print(f"DEBUG: Получен ответ от ИИ длиной {len(result) if result else 0}")
        
        if result and len(result.strip()) > 100:
            # Проверяем качество ответа
            quality_score = check_response_quality(result)
            print(f"DEBUG: Качество ответа: {quality_score}/100")
            
            if quality_score >= 70:
                print(f"DEBUG: Успешно получили качественный план от ИИ")
                print(f"DEBUG: Первые 200 символов ответа: {result[:200]}...")
                print(f"DEBUG: Последние 200 символов ответа: ...{result[-200:]}")
                print(f"DEBUG: Полный ответ от ИИ:")
                print("=" * 80)
                print(result)
                print("=" * 80)
                return result
            else:
                print(f"DEBUG: Ответ неполный (качество {quality_score}/100), используем резервный план")
                return generate_fallback_plan(budget_info, "Ответ от ИИ неполный")
        else:
            print(f"DEBUG: Получен пустой или слишком короткий ответ от ИИ")
            return generate_fallback_plan(budget_info, "Пустой ответ от ИИ")
            
    except Exception as e:
        error_msg = str(e)
        print(f"DEBUG: Ошибка при обращении к ИИ: {error_msg}")
        
        # Проверяем тип ошибки
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            print(f"DEBUG: Обнаружен таймаут, используем резервный план")
            return generate_fallback_plan(budget_info, "Превышено время ожидания ответа от ИИ")
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            print(f"DEBUG: Обнаружен rate limit, используем резервный план")
            return generate_fallback_plan(budget_info, "Превышен лимит запросов к ИИ")
        else:
            print(f"DEBUG: Неизвестная ошибка, используем резервный план")
            return generate_fallback_plan(budget_info, f"Ошибка ИИ: {error_msg}")


def check_response_quality(text: str) -> int:
    """Проверить качество ответа от ИИ (0-100)"""
    if not text:
        return 0
    
    score = 0
    text_lower = text.lower()
    
    # Проверяем наличие ключевых разделов
    required_sections = [
        ('список покупок', 20),
        ('покупки', 20),
        ('инструкции', 20),
        ('готовк', 20),
        ('калории', 15),
        ('стоимость', 15),
        ('цена', 10),
        ('рубл', 10),
        ('₽', 10),
    ]
    
    for section, points in required_sections:
        if section in text_lower:
            score += points
    
    # Проверяем длину ответа
    if len(text) > 500:
        score += 10
    if len(text) > 1000:
        score += 10
    if len(text) > 2000:
        score += 10
    
    # Проверяем структуру (наличие списков, разделов)
    if '•' in text or '-' in text:
        score += 5
    if '\n\n' in text:
        score += 5
    
    # Ограничиваем максимальный балл
    return min(score, 100)


def generate_fallback_plan(budget_info: dict = None, error_msg: str = "") -> str:
    """Создать резервный план питания при ошибке ИИ"""
    budget_text = ""
    daily_budget = 0
    
    if budget_info and budget_info["type"]:
        daily_budget = budget_info["amount"] / 30
        budget_text = f"\n\n💰 <b>Бюджет:</b> {budget_info['description']} (~{daily_budget:.0f} ₽/день)"
    
    error_info = f"\n\n⚠️ <b>Примечание:</b> План сгенерирован автоматически (ИИ недоступен: {error_msg})"
    
    # Адаптируем план под бюджет и цели
    goal_info = ""
    if budget_info and budget_info.get("body_goal"):
        goal_text = budget_info["body_goal"]
        if goal_text == "cut":
            goal_info = "\n\n🎯 <b>Цель:</b> Сушка (снижение веса)\n"
        elif goal_text == "bulk":
            goal_info = "\n\n🎯 <b>Цель:</b> Набор массы\n"
        elif goal_text == "maintain":
            goal_info = "\n\n🎯 <b>Цель:</b> Поддержание веса\n"
    
    if budget_info and budget_info.get("target_calories"):
        goal_info += f"🔥 <b>Целевые калории:</b> {budget_info['target_calories']} в день\n"
    
    if daily_budget > 0:
        if daily_budget < 200:  # Очень экономный
            products = """• Гречка - 1 кг (120-180 ₽)
• Рис - 500 г (80-120 ₽)
• Макароны - 1 кг (120-180 ₽)
• Яйца - 15 шт (120-180 ₽)
• Картофель - 3 кг (180-300 ₽)
• Морковь - 1 кг (60-100 ₽)
• Лук - 1 кг (40-80 ₽)
• Чеснок - 2 головки (40-80 ₽)
• Томатная паста - 200 г (60-100 ₽)
• Масло подсолнечное - 500 мл (80-120 ₽)
• Соль, специи - (50-100 ₽)"""
            total_cost = "800-1200 ₽"
        elif daily_budget < 400:  # Экономный
            products = """• Курица грудка - 1 кг (400-600 ₽)
• Рис - 500 г (80-120 ₽)
• Гречка - 500 г (100-150 ₽)
• Макароны - 500 г (60-100 ₽)
• Яйца - 10 шт (80-120 ₽)
• Картофель - 2 кг (120-200 ₽)
• Морковь - 1 кг (60-100 ₽)
• Лук - 1 кг (40-80 ₽)
• Чеснок - 2 головки (40-80 ₽)
• Томатная паста - 200 г (60-100 ₽)
• Масло подсолнечное - 500 мл (80-120 ₽)
• Соль, специи - (50-100 ₽)"""
            total_cost = "1200-1800 ₽"
        else:  # Стандартный
            products = """• Курица грудка - 1.5 кг (600-900 ₽)
• Свинина - 500 г (300-450 ₽)
• Рис - 1 кг (160-240 ₽)
• Гречка - 500 г (100-150 ₽)
• Макароны - 500 г (60-100 ₽)
• Яйца - 15 шт (120-180 ₽)
• Картофель - 2 кг (120-200 ₽)
• Морковь - 1 кг (60-100 ₽)
• Лук - 1 кг (40-80 ₽)
• Чеснок - 2 головки (40-80 ₽)
• Томатная паста - 300 г (90-150 ₽)
• Масло подсолнечное - 500 мл (80-120 ₽)
• Соль, специи - (50-100 ₽)"""
            total_cost = "1800-2500 ₽"
    else:
        # Если бюджет не установлен, используем стандартный план
        products = """• Курица грудка - 1 кг (400-600 ₽)
• Рис - 500 г (80-120 ₽)
• Гречка - 500 г (100-150 ₽)
• Макароны - 500 г (60-100 ₽)
• Яйца - 10 шт (80-120 ₽)
• Картофель - 2 кг (120-200 ₽)
• Морковь - 1 кг (60-100 ₽)
• Лук - 1 кг (40-80 ₽)
• Чеснок - 2 головки (40-80 ₽)
• Томатная паста - 200 г (60-100 ₽)
• Масло подсолнечное - 500 мл (80-120 ₽)
• Соль, специи - (50-100 ₽)"""
        total_cost = "1200-1800 ₽"
    
    return f"""🍽️ <b>План питания на 2 дня</b>{budget_text}{goal_info}

📋 <b>Список покупок:</b>
{products}

👨‍🍳 <b>Инструкции готовки:</b>

<b>День 1 - Куриная грудка с рисом и овощами:</b>
• Обжарьте куриную грудку на среднем огне 15-20 минут
• Отварите рис (1 стакан на 2 стакана воды)
• Нарежьте овощи и обжарьте их 5-7 минут
• Подавайте с гарниром

<b>День 2 - Гречка с курицей и салатом:</b>
• Отварите гречку (1 стакан на 2 стакана воды)
• Разогрейте куриную грудку
• Приготовьте салат из свежих овощей
• Заправьте салат маслом и лимонным соком

🔥 <b>Калории:</b> 1800-2200 ккал/день
💵 <b>Общая стоимость:</b> {total_cost}

💡 <b>Советы:</b>
• Готовьте на 2 дня вперед
• Используйте остатки для новых блюд
• Замораживайте готовые блюда{error_info}"""
