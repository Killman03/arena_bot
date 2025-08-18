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
    waiting_calories = State()
    waiting_goal = State()


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
        plan_text = await _generate_cooking_plan()
        session.add(CookingSession(user_id=db_user.id, cooking_date=date.today(), instructions=plan_text))
    # Сначала заголовок, затем контент двумя сообщениями, чтобы не упереться в лимит 4096 символов
    await cb.message.edit_text("👨‍🍳 План готовки на 3 дня:", reply_markup=back_main_menu(), parse_mode=None)
    parts = _split_into_two_messages(plan_text)
    if parts:
        await cb.message.answer(parts[0], parse_mode=None)
    if len(parts) > 1:
        await cb.message.answer(parts[1], parse_mode=None)


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
    await state.set_state(NutritionTimeFSM.waiting_calories)
    await message.answer("Укажите целевые калории в день (число) или '-' чтобы пропустить:")


@router.message(NutritionTimeFSM.waiting_calories)
async def set_calories(message: types.Message, state: FSMContext) -> None:
    calories_text = (message.text or "").strip()
    calories = int(calories_text) if calories_text.isdigit() else None
    await state.update_data(calories=calories)
    await state.set_state(NutritionTimeFSM.waiting_goal)
    await message.answer("Цель: cut/bulk/maintain или '-' чтобы пропустить:")


@router.message(NutritionTimeFSM.waiting_goal)
async def set_goal(message: types.Message, state: FSMContext) -> None:
    goal_text = (message.text or "").strip().lower()
    goal = goal_text if goal_text in {"cut", "bulk", "maintain"} else None
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
        reminder.cooking_days = data["days"]
        reminder.cooking_time = data["cook_time"]
        reminder.reminder_time = data["remind_time"]
        reminder.shopping_reminder_time = data["shop_time"]
        reminder.target_calories = data.get("calories")
        reminder.body_goal = goal
    await state.clear()
    await message.answer("Настройки напоминаний сохранены ✅", reply_markup=back_main_menu())


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


async def _generate_cooking_plan() -> str:
    system = (
        "Ты нутрициолог и кулинар. Составь план готовки на 3 дня из доступных и недорогих продуктов, "
        "сбалансированное полезное питание. Дай: список покупок с количеством, суммарные калории на день и простые инструкции."
    )
    prompt = "Сделай список покупок и инструкции на 3 дня. Формат: Покупки, Инструкции, Калории/день."
    try:
        return await deepseek_complete(prompt, system=system, max_tokens=700)
    except Exception as e:
        return f"Не удалось получить план от ИИ: {e}"


def _split_into_two_messages(text: str, max_len: int = 3800) -> list[str]:
    """Разбить текст максимум на два сообщения, оба не длиннее max_len.
    Если общий текст > 2*max_len, вторая часть будет усечена с многоточием.
    """
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    # Идеальная точка разреза — близко к середине по абзацам
    paragraphs = text.split("\n\n")
    total_len = len(text)
    target = total_len // 2
    part1 = []
    len1 = 0
    for p in paragraphs:
        block = p + "\n\n"
        if len1 + len(block) <= max_len and (len1 + len(block) <= target or len1 == 0):
            part1.append(block)
            len1 += len(block)
        else:
            break
    part1_text = "".join(part1).rstrip()
    rest = text[len(part1_text):].lstrip()
    if not part1_text:
        # если первый абзац огромный, режем по строкам/символам
        part1_text = text[:max_len]
        rest = text[max_len:]
    # Обеспечим лимит второй части
    if len(rest) <= max_len:
        return [part1_text, rest] if rest else [part1_text]
    # Слишком длинно — усечем вторую часть
    part2_text = rest[:max_len - 1] + "…"
    return [part1_text, part2_text]






