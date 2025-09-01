from __future__ import annotations

from datetime import date

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, desc

from app.db.models import MealPlan, MealType, User, CookingSession, NutritionReminder
from app.db.session import session_scope
from app.keyboards.common import back_main_menu
from app.services.llm import deepseek_complete
from app.handlers.nutrition_budget import get_user_food_budget
from app.utils.timezone_utils import get_user_time_info

router = Router()


@router.message(Command("meal"))
async def plan_meal(message: types.Message) -> None:
    """Plan a meal: /meal breakfast Омлет [YYYY-MM-DD]."""
    user = message.from_user
    if not user:
        return
    payload = (message.text or "").replace("/meal", "", 1).strip()
    if not payload:
        await message.answer("Использование: /meal breakfast Название [YYYY-MM-DD]")
        return
    parts = payload.split()
    meal_type = MealType(parts[0])
    title = " ".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
    d = parts[-1]
    try:
        plan_date = date.fromisoformat(d)
    except Exception:
        plan_date = date.today()
        title = " ".join(parts[1:])

    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        session.add(MealPlan(user_id=db_user.id, date=plan_date, type=meal_type, title=title))
    await message.answer("Прием пищи запланирован ✅")


class NutritionTimeFSM(StatesGroup):
    waiting_days = State()
    waiting_cook_time = State()
    waiting_remind_time = State()
    waiting_shop_time = State()


@router.callback_query(F.data == "nutrition_cooking_now")
async def nutrition_cooking_now(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    # Ответить на callback сразу, чтобы не истек таймаут Telegram
    try:
        await cb.answer("Готовлю план...", show_alert=False)
    except Exception:
        pass
    # Быстро обновим сообщение, чтобы показать прогресс
    try:
        await cb.message.edit_text("⏳ Генерирую план готовки...", reply_markup=back_main_menu())
    except Exception:
        pass
        
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Получаем информацию о бюджете питания пользователя
        budget_info = await get_user_food_budget(session, db_user.id)
        print(f"DEBUG: budget_info = {budget_info}")  # Временное логирование
        
        # Обновляем сообщение о прогрессе
        try:
            await cb.message.edit_text("🤖 Обращаюсь к ИИ для генерации плана...", reply_markup=back_main_menu())
        except Exception:
            pass
        
        # Генерируем план питания
        try:
            from app.services.nutrition_plan_generator import generate_cooking_plan, generate_fallback_plan
            plan_text = await generate_cooking_plan(budget_info)
            if not plan_text or len(plan_text.strip()) < 10:
                plan_text = generate_fallback_plan(budget_info, "Пустой ответ от ИИ")
        except Exception as e:
            print(f"DEBUG: Ошибка в generate_cooking_plan: {e}")
            plan_text = generate_fallback_plan(budget_info, str(e))
        
        # Сохраняем в базу
        session.add(CookingSession(user_id=db_user.id, cooking_date=date.today(), instructions=plan_text))
        await session.commit()
    # Сначала заголовок с информацией о бюджете, затем контент двумя сообщениями
    budget_text = f" (бюджет: {budget_info['description']})" if budget_info and budget_info["type"] else ""
    header_text = f"👨‍🍳 План готовки на 2 дня{budget_text}:"
    await cb.message.edit_text(header_text, reply_markup=back_main_menu(), parse_mode="HTML")
    
    # Конвертируем Markdown в HTML для корректного отображения
    plan_text_html = _convert_markdown_to_html(plan_text)
    
    # Разбиваем на части и отправляем
    print(f"DEBUG: Длина плана после HTML конвертации: {len(plan_text_html)} символов")
    print(f"DEBUG: Первые 200 символов HTML плана: {plan_text_html[:200]}...")
    print(f"DEBUG: Последние 200 символов HTML плана: ...{plan_text_html[-200:]}")
    
    parts = _split_into_multiple_messages(plan_text_html)
    print(f"DEBUG: План разбит на {len(parts)} частей")
    
    # Отправляем все части
    for i, part in enumerate(parts):
        print(f"DEBUG: Отправляю часть {i+1} длиной {len(part)} символов")
        print(f"DEBUG: Содержимое части {i+1}:")
        print("-" * 40)
        print(part)
        print("-" * 40)
        await cb.message.answer(part, parse_mode="HTML")


@router.callback_query(F.data == "nutrition_body_recomp")
async def nutrition_body_recomp(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        reminder = (
            await session.execute(select(NutritionReminder).where(NutritionReminder.user_id == db_user.id))
        ).scalar_one_or_none()
    text = (
        (f"Текущие настройки: goal={reminder.body_goal if reminder else '-'}, "
         f"calories={reminder.target_calories if reminder else '-'}\n\n")
        if reminder else ""
    )
    text += (
        "💪 Режим тела\n\n"
        "Выберите цель: cut (сушка) / bulk (масса) / maintain (поддержание).\n"
        "И, при желании, укажите целевые калории, например: 2400.\n\n"
        "Отправьте сообщение в формате:\n"
        "goal calories\n"
        "Примеры:\n"
        "cut 2100\n"
        "bulk 3000\n"
        "maintain 2500\n"
    )
    await cb.message.edit_text(text)
    await cb.answer()


@router.message(F.text.regexp(r"^(cut|bulk|maintain)(\s+\d{3,5})?$"))
async def nutrition_body_recomp_set(message: types.Message) -> None:
    user = message.from_user
    if not user:
        return
    parts = message.text.split()
    goal = parts[0]
    calories = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        reminder = (
            await session.execute(select(NutritionReminder).where(NutritionReminder.user_id == db_user.id))
        ).scalar_one_or_none()
        if not reminder:
            reminder = NutritionReminder(user_id=db_user.id)
            session.add(reminder)
        reminder.body_goal = goal
        reminder.target_calories = calories
    await message.answer("Настройки режима сохранены ✅", reply_markup=back_main_menu())


@router.callback_query(F.data == "nutrition_time_settings")
async def nutrition_time_settings(cb: types.CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NutritionTimeFSM.waiting_days)
    await cb.message.edit_text(
        "⏰ Настройка времени готовки\n\n"
        "Введите дни недели через запятую для готовки (например: sunday,wednesday):",
        reply_markup=back_main_menu(),
    )
    await cb.answer()


@router.message(NutritionTimeFSM.waiting_days)
async def set_days(message: types.Message, state: FSMContext) -> None:
    await state.update_data(days=message.text.lower())
    await state.set_state(NutritionTimeFSM.waiting_cook_time)
    await message.answer("Введите время готовки (HH:MM), например 18:00:")


@router.message(NutritionTimeFSM.waiting_cook_time)
async def set_cook_time(message: types.Message, state: FSMContext) -> None:
    await state.update_data(cook_time=message.text)
    await state.set_state(NutritionTimeFSM.waiting_remind_time)
    await message.answer("Введите время напоминания в день готовки (HH:MM), например 17:00:")


@router.message(NutritionTimeFSM.waiting_remind_time)
async def set_remind_time(message: types.Message, state: FSMContext) -> None:
    await state.update_data(remind_time=message.text)
    await state.set_state(NutritionTimeFSM.waiting_shop_time)
    await message.answer("Введите время напоминания о покупках за день до готовки (HH:MM), например 16:00:")


@router.message(NutritionTimeFSM.waiting_shop_time)
async def set_shop_time(message: types.Message, state: FSMContext) -> None:
    await state.update_data(shop_time=message.text)
    data = await state.get_data()
    user = message.from_user
    if not user:
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        reminder = (
            await session.execute(select(NutritionReminder).where(NutritionReminder.user_id == db_user.id))
        ).scalar_one_or_none()
        if not reminder:
            reminder = NutritionReminder(user_id=db_user.id)
            session.add(reminder)
        
        # Логируем локальное время пользователя при создании напоминания
        time_info = get_user_time_info(db_user.timezone)
        print(f"🕐 Создание напоминания о питании пользователем {db_user.telegram_id}")
        print(f"   📍 Часовой пояс: {time_info['timezone']}")
        print(f"   🕐 Локальное время пользователя: {time_info['user_local_time'].strftime('%H:%M:%S')}")
        print(f"   🌍 UTC время: {time_info['utc_time'].strftime('%H:%M:%S')}")
        print(f"   ⏰ Время готовки: {data['cook_time']}")
        print(f"   ⏰ Время напоминания: {data['remind_time']}")
        print(f"   🛒 Время покупок: {data['shop_time']}")
        print(f"   📊 Смещение: {time_info['offset_hours']:+g} ч")
        
        reminder.cooking_days = data["days"]
        reminder.cooking_time = data["cook_time"]
        reminder.reminder_time = data["remind_time"]
        reminder.shopping_reminder_time = data["shop_time"]
        # Не изменяем target_calories и body_goal - они настраиваются отдельно
    await state.clear()
    await message.answer("Настройки времени напоминаний сохранены ✅", reply_markup=back_main_menu())





@router.callback_query(F.data == "nutrition_history")
async def nutrition_history(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        sessions = (
            await session.execute(
                select(CookingSession)
                .where(CookingSession.user_id == db_user.id)
                .order_by(desc(CookingSession.cooking_date))
                .limit(5)
            )
        ).scalars().all()
    if not sessions:
        await cb.message.edit_text("История пуста.", reply_markup=back_main_menu())
        await cb.answer()
        return
    text = "📋 Последние готовки:\n\n"
    for s in sessions:
        text += f"- {s.cooking_date.isoformat()} — {('есть инструкции' if s.instructions else 'без инструкций')}\n"
    await cb.message.edit_text(text, reply_markup=back_main_menu())
    await cb.answer()


async def _generate_cooking_plan(budget_info: dict = None) -> str:
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
    
    system = (
        f"Ты нутрициолог и кулинар. {budget_context}"
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
            quality_score = _check_response_quality(result)
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
                return _generate_fallback_plan(budget_info, "Ответ от ИИ неполный")
        else:
            print(f"DEBUG: Получен пустой или слишком короткий ответ от ИИ")
            return _generate_fallback_plan(budget_info, "Пустой ответ от ИИ")
            
    except Exception as e:
        error_msg = str(e)
        print(f"DEBUG: Ошибка при обращении к ИИ: {error_msg}")
        
        # Проверяем тип ошибки
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            print(f"DEBUG: Обнаружен таймаут, используем резервный план")
            return _generate_fallback_plan(budget_info, "Превышено время ожидания ответа от ИИ")
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            print(f"DEBUG: Обнаружен rate limit, используем резервный план")
            return _generate_fallback_plan(budget_info, "Превышен лимит запросов к ИИ")
        else:
            print(f"DEBUG: Неизвестная ошибка, используем резервный план")
            return _generate_fallback_plan(budget_info, f"Ошибка ИИ: {error_msg}")


def _check_response_quality(text: str) -> int:
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
        ('день 1', 15),
        ('день 2', 15)
    ]
    
    for section, points in required_sections:
        if section in text_lower:
            score += points
    
    # Проверяем длину ответа
    if len(text) > 1000:
        score += 20
    elif len(text) > 500:
        score += 10
    
    # Проверяем структурированность (наличие эмодзи и разделителей)
    if '📋' in text or '🛒' in text or '👨‍🍳' in text or '🔥' in text or '💵' in text:
        score += 15
    
    # Проверяем наличие конкретных данных
    if any(char.isdigit() for char in text):  # Есть числа (цены, калории)
        score += 10
    
    # Ограничиваем максимальный балл
    return min(score, 100)


def _generate_fallback_plan(budget_info: dict = None, error_msg: str = "") -> str:
    """Создать резервный план питания при ошибке ИИ"""
    budget_text = ""
    daily_budget = 0
    
    if budget_info and budget_info["type"]:
        daily_budget = budget_info["amount"] / 30
        budget_text = f"\n\n💰 <b>Бюджет:</b> {budget_info['description']} (~{daily_budget:.0f} ₽/день)"
    
    error_info = f"\n\n⚠️ <b>Примечание:</b> План сгенерирован автоматически (ИИ недоступен: {error_msg})"
    
    # Адаптируем план под бюджет
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
    
    return f"""🍽️ <b>План питания на 2 дня</b>{budget_text}

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


def _split_into_multiple_messages(text: str, max_len: int = 3000) -> list[str]:
    """Разбить текст на столько сообщений, сколько нужно для полного отображения.
    Специально оптимизировано для планов питания от DeepSeek.
    """
    if not text:
        return []
    
    print(f"DEBUG: _split_into_multiple_messages вызвана с текстом длиной {len(text)} символов")
    print(f"DEBUG: max_len = {max_len}")
    
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
        'День 1:', 'День 2:', 'Завтрак:', 'Обед:', 'Ужин:', 'Перекус:'
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
    
    print(f"DEBUG: Логическое разбиение дало {len(parts)} частей")
    
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
    print(f"DEBUG: _split_into_parts_standard вызвана с текстом длиной {len(text)} символов")
    print(f"DEBUG: max_len = {max_len}")
    
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
        
        print(f"DEBUG: Текст не превышает max_len, возвращаю как есть")
        return [text]
    
    # Оптимизируем размер частей для лучшей читаемости
    # Если текст очень длинный, разбиваем на более мелкие части
    optimal_part_size = min(max_len, 2500) if len(text) > 4000 else max_len
    print(f"DEBUG: optimal_part_size = {optimal_part_size}")
    
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
    
    print(f"DEBUG: Стандартное разбиение завершено, получилось {len(parts)} частей")
    return parts


def _convert_markdown_to_html(text: str) -> str:
    """Конвертировать Markdown разметку в HTML теги для Telegram"""
    if not text:
        return text
    
    print(f"DEBUG: _convert_markdown_to_html вызвана с текстом длиной {len(text)} символов")
    
    # Конвертируем **текст** в <b>текст</b>
    import re
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Конвертируем *текст* в <i>текст</i> (курсив)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # Конвертируем `текст` в <code>текст</code> (моноширинный шрифт)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    # Конвертируем ## Заголовок в <b>Заголовок</b>
    text = re.sub(r'^##\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # Конвертируем # Заголовок в <b>Заголовок</b>
    text = re.sub(r'^#\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # Конвертируем - пункт в • пункт (для лучшей читаемости)
    text = re.sub(r'^\s*-\s+', r'• ', text, flags=re.MULTILINE)
    
    # Конвертируем * пункт в • пункт (для лучшей читаемости)
    text = re.sub(r'^\s*\*\s+', r'• ', text, flags=re.MULTILINE)
    
    print(f"DEBUG: После HTML конвертации длина текста: {len(text)} символов")
    
    return text


@router.message(Command("test_nutrition_settings"))
async def test_nutrition_settings(message: types.Message) -> None:
    """Тестирует настройки питания и показывает текущие дни."""
    user = message.from_user
    if not user:
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Получаем настройки питания
            reminder = (await session.execute(
                select(NutritionReminder).where(NutritionReminder.user_id == db_user.id)
            )).scalar_one_or_none()
            
            if not reminder:
                await message.answer("❌ Настройки питания не найдены. Сначала настройте напоминания о питании.")
                return
            
            # Получаем информацию о времени пользователя
            from app.utils.timezone_utils import get_user_time_info
            time_info = get_user_time_info(db_user.timezone)
            
            # Парсируем дни
            days = [d.strip().lower() for d in (reminder.cooking_days or "").split(",") if d.strip()]
            weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            current_day_name = weekday_names[time_info['user_local_time'].weekday()]
            
            # Проверяем, является ли сегодня днем готовки
            from app.services.nutrition_reminders import _weekday_str_to_int
            is_cooking_day = time_info['user_local_time'].weekday() in [
                _weekday_str_to_int(d) for d in days if d in {"sunday", "wednesday", "monday", "tuesday", "thursday", "friday", "saturday"}
            ]
            
            # Проверяем, является ли завтра днем готовки (для покупок)
            tomorrow_weekday = (time_info['user_local_time'].weekday() + 1) % 7
            tomorrow_day_name = weekday_names[tomorrow_weekday]
            is_shopping_day = tomorrow_weekday in [
                _weekday_str_to_int(d) for d in days if d in {"sunday", "wednesday", "monday", "tuesday", "thursday", "friday", "saturday"}
            ]
            
            status_text = f"""📊 <b>Настройки питания</b>

👤 <b>Пользователь:</b> {db_user.telegram_id}
📍 <b>Часовой пояс:</b> {time_info['timezone']}
🕐 <b>Локальное время:</b> {time_info['user_local_time'].strftime('%d.%m.%Y %H:%M')}

📅 <b>Дни готовки:</b> {reminder.cooking_days or 'Не настроено'}
⏰ <b>Время готовки:</b> {reminder.cooking_time or 'Не настроено'}
⏰ <b>Время напоминания:</b> {reminder.reminder_time or 'Не настроено'}
🛒 <b>Время покупок:</b> {reminder.shopping_reminder_time or 'Не настроено'}
🎯 <b>Цель:</b> {reminder.body_goal or 'Не настроено'}
🔥 <b>Калории:</b> {reminder.target_calories or 'Не настроено'}

📊 <b>Статус сегодня:</b>
• Сегодня ({current_day_name}): {'✅ День готовки' if is_cooking_day else '❌ Не день готовки'}
• Завтра ({tomorrow_day_name}): {'✅ День готовки (сегодня покупки)' if is_shopping_day else '❌ Не день готовки'}

🔧 <b>Парсированные дни:</b> {days}
🔧 <b>Номера дней недели:</b> {[_weekday_str_to_int(d) for d in days if d in {'sunday', 'wednesday', 'monday', 'tuesday', 'thursday', 'friday', 'saturday'}]}"""
            
            await message.answer(status_text, parse_mode="HTML")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка получения настроек питания: {str(e)}")






