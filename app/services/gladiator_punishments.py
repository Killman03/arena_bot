from __future__ import annotations
from typing import List, Dict, Any
from app.services.llm import deepseek_complete


async def generate_gladiator_punishment(
    overdue_goals: List[Dict[str, Any]],
    overdue_challenges: List[Dict[str, Any]],
    overdue_todos: List[Dict[str, Any]]
) -> str:
    """
    Генерирует гладиаторское наказание для просроченных дедлайнов
    
    Args:
        overdue_goals: Список просроченных целей
        overdue_challenges: Список просроченных челленджей  
        overdue_todos: Список просроченных задач
    
    Returns:
        Текст наказания в стиле гладиаторской арены
    """
    
    # Формируем описание просроченных дел
    overdue_items = []
    
    if overdue_goals:
        goals_text = "🎯 Просроченные цели:\n"
        for goal in overdue_goals:
            days_overdue = goal.get('days_overdue', 0)
            goals_text += f"• {goal['title']} (просрочено на {days_overdue} дней)\n"
        overdue_items.append(goals_text)
    
    if overdue_challenges:
        challenges_text = "🏆 Просроченные челленджи:\n"
        for challenge in overdue_challenges:
            days_overdue = challenge.get('days_overdue', 0)
            challenges_text += f"• {challenge['title']} (просрочено на {days_overdue} дней)\n"
        overdue_items.append(challenges_text)
    
    if overdue_todos:
        todos_text = "📝 Просроченные задачи:\n"
        for todo in overdue_todos:
            days_overdue = todo.get('days_overdue', 0)
            todos_text += f"• {todo['title']} (просрочено на {days_overdue} дней)\n"
        overdue_items.append(todos_text)
    
    overdue_summary = "\n".join(overdue_items)
    
    # Системный промпт для ИИ
    system_prompt = """Ты - суровый гладиаторский тренер на арене жизни. Твоя задача - придумать достойное наказание для гладиатора, который просрочил дедлайны.

ПРАВИЛА:
1. Наказание должно быть в духе гладиаторской арены
2. Используй образы: мечи, щиты, арена, тренировки, выносливость
3. Наказание должно быть выполнимым и полезным
4. Добавь мотивацию и объяснение, почему это наказание поможет
5. Используй эмодзи для атмосферы
6. Пиши в стиле сурового, но справедливого тренера
7. Избегай HTML-тегов, используй обычный текст

СТРУКТУРА ОТВЕТА:
1. Суровое обращение к гладиатору
2. Анализ просроченных дел
3. Наказание с объяснением
4. Мотивация и план исправления
5. Гладиаторский девиз

Пример стиля:
"⚔️ ГЛАДИАТОР! Ты осрамил честь арены своими просрочками! 
На арене жизни нет места слабости и недисциплинированности..."

Генерируй наказание на основе предоставленной информации о просроченных делах."""

    # Пользовательский промпт
    user_prompt = f"""Гладиатор просрочил следующие дела:

{overdue_summary}

Придумай достойное наказание в стиле гладиаторской арены!"""

    try:
        # Объединяем системный и пользовательский промпт
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        punishment = await deepseek_complete(
            prompt=full_prompt,
            max_tokens=800
        )
        return punishment
    except Exception as e:
        # Fallback наказание
        return f"""⚔️ ГЛАДИАТОР! Ты осрамил честь арены!

{overdue_summary}

🏛️ НАКАЗАНИЕ АРЕНЫ:
• 3 дня усиленных тренировок по 2 часа
• Ежедневная медитация на дисциплину
• Пересмотр всех дедлайнов и создание буферов

💪 Помни: на арене жизни нет места слабости! 
Исправляйся или покидай арену!"""
