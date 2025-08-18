from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StateMachine
from sqlalchemy import select
from datetime import datetime

from app.db.session import session_scope
from app.db.models import User, HealthMetric, HealthGoal, HealthReminder

router = Router()


class HealthStates(StateMachine):
    waiting_for_metric_type = State()
    waiting_for_metric_value = State()
    waiting_for_metric_unit = State()
    waiting_for_goal_type = State()
    waiting_for_goal_target = State()
    waiting_for_reminder_type = State()
    waiting_for_reminder_message = State()


@router.message(Command("health"))
async def health_menu(message: types.Message) -> None:
    """Show health menu"""
    health_text = """
🏥 **Меню здоровья**

📊 **Команды для отслеживания**:
• /health_metric - Добавить метрику здоровья
• /health_goal - Поставить цель по здоровью
• /health_reminder - Установить напоминание
• /health_stats - Показать статистику

💡 **Примеры метрик**: вес, шаги, пульс, давление
"""
    await message.answer(health_text)


@router.message(Command("health_metric"))
async def start_health_metric(message: types.Message, state: FSMContext) -> None:
    """Start adding health metric"""
    await state.set_state(HealthStates.waiting_for_metric_type)
    await message.answer("Введите тип метрики (например: вес, шаги, пульс):")


@router.message(HealthStates.waiting_for_metric_type)
async def get_metric_type(message: types.Message, state: FSMContext) -> None:
    """Get metric type and ask for value"""
    await state.update_data(metric_type=message.text)
    await state.set_state(HealthStates.waiting_for_metric_value)
    await message.answer("Введите значение метрики:")


@router.message(HealthStates.waiting_for_metric_value)
async def get_metric_value(message: types.Message, state: FSMContext) -> None:
    """Get metric value and ask for unit"""
    try:
        value = float(message.text)
        await state.update_data(metric_value=value)
        await state.set_state(HealthStates.waiting_for_metric_unit)
        await message.answer("Введите единицу измерения (например: кг, шаги, уд/мин) или 'нет' если не нужно:")
    except ValueError:
        await message.answer("Пожалуйста, введите числовое значение.")


@router.message(HealthStates.waiting_for_metric_unit)
async def save_health_metric(message: types.Message, state: FSMContext) -> None:
    """Save health metric to database"""
    user = message.from_user
    if not user:
        return

    data = await state.get_data()
    metric_type = data.get("metric_type")
    metric_value = data.get("metric_value")
    unit = message.text if message.text.lower() != "нет" else None

    async with session_scope() as session:
        # Get user from database
        db_user = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = db_user.scalar_one_or_none()
        
        if not db_user:
            await message.answer("Пользователь не найден. Сначала зарегистрируйтесь с помощью /start")
            await state.clear()
            return

        # Create health metric
        health_metric = HealthMetric(
            user_id=db_user.id,
            metric_type=metric_type,
            value=metric_value,
            unit=unit
        )
        session.add(health_metric)
        await session.commit()

    await message.answer(f"✅ Метрика '{metric_type}' со значением {metric_value} {unit or ''} сохранена!")
    await state.clear()


@router.message(Command("health_stats"))
async def show_health_stats(message: types.Message) -> None:
    """Show health statistics"""
    user = message.from_user
    if not user:
        return

    async with session_scope() as session:
        # Get user from database
        db_user = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = db_user.scalar_one_or_none()
        
        if not db_user:
            await message.answer("Пользователь не найден. Сначала зарегистрируйтесь с помощью /start")
            return

        # Get health metrics count
        metrics_count = await session.execute(
            select(HealthMetric).where(HealthMetric.user_id == db_user.id)
        )
        metrics = metrics_count.scalars().all()

        if not metrics:
            await message.answer("У вас пока нет записей о здоровье. Используйте /health_metric для добавления.")
            return

        # Group metrics by type
        metrics_by_type = {}
        for metric in metrics:
            if metric.metric_type not in metrics_by_type:
                metrics_by_type[metric.metric_type] = []
            metrics_by_type[metric.metric_type].append(metric)

        stats_text = "📊 **Статистика здоровья**\n\n"
        
        for metric_type, type_metrics in metrics_by_type.items():
            latest_metric = max(type_metrics, key=lambda x: x.recorded_at)
            stats_text += f"**{metric_type}**: {latest_metric.value} {latest_metric.unit or ''}\n"
            stats_text += f"Последнее измерение: {latest_metric.recorded_at.strftime('%d.%m.%Y %H:%M')}\n\n"

        await message.answer(stats_text)


@router.message(Command("health_goal"))
async def start_health_goal(message: types.Message, state: FSMContext) -> None:
    """Start setting health goal"""
    await state.set_state(HealthStates.waiting_for_goal_type)
    await message.answer("Введите тип цели по здоровью (например: похудение, набор мышечной массы):")


@router.message(HealthStates.waiting_for_goal_type)
async def get_goal_type(message: types.Message, state: FSMContext) -> None:
    """Get goal type and ask for target value"""
    await state.update_data(goal_type=message.text)
    await state.set_state(HealthStates.waiting_for_goal_target)
    await message.answer("Введите целевое значение (например: 75 для веса в кг):")


@router.message(HealthStates.waiting_for_goal_target)
async def save_health_goal(message: types.Message, state: FSMContext) -> None:
    """Save health goal to database"""
    user = message.from_user
    if not user:
        return

    try:
        target_value = float(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите числовое значение.")
        return

    data = await state.get_data()
    goal_type = data.get("goal_type")

    async with session_scope() as session:
        # Get user from database
        db_user = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = db_user.scalar_one_or_none()
        
        if not db_user:
            await message.answer("Пользователь не найден. Сначала зарегистрируйтесь с помощью /start")
            await state.clear()
            return

        # Create health goal
        health_goal = HealthGoal(
            user_id=db_user.id,
            goal_type=goal_type,
            target_value=target_value
        )
        session.add(health_goal)
        await session.commit()

    await message.answer(f"✅ Цель '{goal_type}' с целевым значением {target_value} установлена!")
    await state.clear()
