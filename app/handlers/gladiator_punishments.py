from __future__ import annotations

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, date
from sqlalchemy import select, func
from app.db.session import session_scope
from app.db.models import User, Goal, GoalStatus, Todo
from app.services.gladiator_punishments import generate_gladiator_punishment

router = Router()


@router.message(Command("arena_punishment"))
async def arena_punishment_command(message: types.Message) -> None:
    """Команда для получения гладиаторского наказания за просроченные дела"""
    await check_arena_punishment(message)


@router.callback_query(F.data == "arena_punishment")
async def arena_punishment_callback(cb: types.CallbackQuery) -> None:
    """Обработчик кнопки "Арена жизни" в главном меню"""
    # Сразу отвечаем на callback query, чтобы избежать ошибки "query is too old"
    await cb.answer()
    await check_arena_punishment(cb.message, cb.from_user)


async def check_arena_punishment(message_or_cb, user=None) -> None:
    """Основная функция проверки арены жизни"""
    if user is None:
        user = message_or_cb.from_user
    
    if not user:
        return
    
    # Показываем сообщение о том, что проверяем арену
    if hasattr(message_or_cb, 'edit_text'):
        # Это callback query
        status_message = message_or_cb
        await message_or_cb.edit_text(
            "⚔️ <b>Проверяю арену жизни...</b>\n\n"
            "🔍 Ищу просроченные дела гладиатора...",
            parse_mode="HTML"
        )
    else:
        # Это обычное сообщение
        status_message = await message_or_cb.answer(
            "⚔️ <b>Проверяю арену жизни...</b>\n\n"
            "🔍 Ищу просроченные дела гладиатора...",
            parse_mode="HTML"
        )
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == user.id)
            )).scalar_one()
            
            today = date.today()
            overdue_items = {
                'goals': [],
                'todos': []
            }
            
            # Проверяем просроченные цели
            overdue_goals = (await session.execute(
                select(Goal).where(
                    Goal.user_id == db_user.id,
                    Goal.status == GoalStatus.active,
                    Goal.due_date.is_not(None),
                    Goal.due_date < today
                )
            )).scalars().all()
            
            for goal in overdue_goals:
                days_overdue = (today - goal.due_date).days
                overdue_items['goals'].append({
                    'title': goal.title,
                    'deadline': goal.due_date,
                    'days_overdue': days_overdue
                })
            

            
            # Проверяем просроченные задачи
            overdue_todos = (await session.execute(
                select(Todo).where(
                    Todo.user_id == db_user.id,
                    Todo.is_completed == False,
                    Todo.due_date < today
                )
            )).scalars().all()
            
            for todo in overdue_todos:
                days_overdue = (today - todo.due_date).days
                overdue_items['todos'].append({
                    'title': todo.title,
                    'due_date': todo.due_date,
                    'days_overdue': days_overdue
                })
            
            total_overdue = (
                len(overdue_items['goals']) + 
                len(overdue_items['todos'])
            )
            
            if total_overdue == 0:
                await status_message.edit_text(
                    "🏆 <b>ГЛАДИАТОР ДОСТОИН ЧЕСТИ АРЕНЫ!</b>\n\n"
                    "⚔️ Все дедлайны соблюдены!\n"
                    "🛡️ Твоя дисциплина безупречна!\n"
                    "👑 Продолжай в том же духе!",
                    parse_mode="HTML"
                )
                return
            
            # Обновляем статус
            if hasattr(status_message, 'edit_text'):
                await status_message.edit_text(
                    f"⚔️ <b>АРЕНА ОБНАРУЖИЛА ПРОСРОЧКИ!</b>\n\n"
                    f"🎯 Просроченных целей: {len(overdue_items['goals'])}\n"
                    f"📝 Просроченных задач: {len(overdue_items['todos'])}\n\n"
                    f"🔍 Генерирую наказание...",
                    parse_mode="HTML"
                )
            else:
                # Для обычных сообщений отправляем новое
                await message_or_cb.answer(
                    f"⚔️ <b>АРЕНА ОБНАРУЖИЛА ПРОСРОЧКИ!</b>\n\n"
                    f"🎯 Просроченных целей: {len(overdue_items['goals'])}\n"
                    f"📝 Просроченных задач: {len(overdue_items['todos'])}\n\n"
                    f"🔍 Генерирую наказание...",
                    parse_mode="HTML"
                )
            
            # Генерируем наказание
            punishment = await generate_gladiator_punishment(
                overdue_goals=overdue_items['goals'],
    
                overdue_todos=overdue_items['todos']
            )
            
            # Создаем клавиатуру для действий
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⚔️ Принять наказание", 
                        callback_data="accept_punishment"
                    ),
                    InlineKeyboardButton(
                        text="🛡️ Исправить дела", 
                        callback_data="fix_overdue_items"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📊 Детальный анализ", 
                        callback_data="overdue_analysis"
                    )
                ]
            ])
            
            # Отправляем наказание
            if hasattr(status_message, 'edit_text'):
                await status_message.edit_text(
                    f"⚔️ <b>ПРИГОВОР АРЕНЫ ВЫНЕСЕН!</b>\n\n{punishment}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Для обычных сообщений отправляем новое
                await message_or_cb.answer(
                    f"⚔️ <b>ПРИГОВОР АРЕНЫ ВЫНЕСЕН!</b>\n\n{punishment}",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            
    except Exception as e:
        if hasattr(status_message, 'edit_text'):
            await status_message.edit_text(
                "❌ <b>Ошибка проверки арены</b>\n\n"
                "Не удалось проверить просроченные дела.\n"
                "Попробуйте позже.",
                parse_mode="HTML"
            )
        else:
            # Для обычных сообщений отправляем новое
            await message_or_cb.answer(
                "❌ <b>Ошибка проверки арены</b>\n\n"
                "Не удалось проверить просроченные дела.\n"
                "Попробуйте позже.",
                parse_mode="HTML"
            )


@router.callback_query(F.data == "accept_punishment")
async def accept_punishment(cb: types.CallbackQuery) -> None:
    """Принятие наказания гладиатором"""
    await cb.message.edit_text(
        "⚔️ <b>ГЛАДИАТОР ПРИНЯЛ НАКАЗАНИЕ!</b>\n\n"
        "🛡️ Твоя честь восстановлена!\n"
        "💪 Теперь выполняй наказание достойно!\n"
        "🏛️ Арена следит за тобой!\n\n"
        "📱 Используй команду /arena_punishment для повторной проверки",
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "fix_overdue_items")
async def fix_overdue_items(cb: types.CallbackQuery) -> None:
    """Переход к исправлению просроченных дел"""
    await cb.message.edit_text(
        "🛡️ <b>ИСПРАВЛЕНИЕ ПРОСРОЧЕННЫХ ДЕЛ</b>\n\n"
        "📋 Выберите раздел для исправления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 Цели", callback_data="fix_goals"),

            ],
            [
                InlineKeyboardButton(text="📝 Задачи", callback_data="fix_todos"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_punishment")
            ]
        ]),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "overdue_analysis")
async def overdue_analysis(cb: types.CallbackQuery) -> None:
    """Детальный анализ просроченных дел"""
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    try:
        async with session_scope() as session:
            db_user = (await session.execute(
                select(User).where(User.telegram_id == user.id)
            )).scalar_one()
            
            today = date.today()
            
            # Получаем детальную статистику
            overdue_goals_count = (await session.execute(
                select(func.count(Goal.id)).where(
                    Goal.user_id == db_user.id,
                    Goal.status == GoalStatus.active,
                    Goal.deadline < today
                )
            )).scalar()
            

            
            overdue_todos_count = (await session.execute(
                select(func.count(Todo.id)).where(
                    Todo.user_id == db_user.id,
                    Todo.is_completed == False,
                    Todo.due_date < today
                )
            )).scalar()
            
            total_overdue = overdue_goals_count + overdue_todos_count
            
            if total_overdue == 0:
                await cb.message.edit_text(
                    "🏆 <b>АНАЛИЗ АРЕНЫ</b>\n\n"
                    "✅ Все дедлайны соблюдены!\n"
                    "🛡️ Дисциплина на высоте!\n"
                    "👑 Продолжай в том же духе!",
                    parse_mode="HTML"
                )
                return
            
            # Рассчитываем процент просрочек
            total_items = (await session.execute(
                select(func.count(Goal.id)).where(
                    Goal.user_id == db_user.id,
                    Goal.status == GoalStatus.active
                )
            )).scalar()
            

            
            total_items += (await session.execute(
                select(func.count(Todo.id)).where(
                    Todo.user_id == db_user.id,
                    Todo.is_completed == False
                )
            )).scalar()
            
            overdue_percentage = (total_overdue / total_items * 100) if total_items > 0 else 0
            
            analysis_text = (
                f"📊 <b>ДЕТАЛЬНЫЙ АНАЛИЗ АРЕНЫ</b>\n\n"
                f"🎯 <b>Цели:</b> {overdue_goals_count} просрочено\n"

                f"📝 <b>Задачи:</b> {overdue_todos_count} просрочено\n\n"
                f"📈 <b>Общая статистика:</b>\n"
                f"• Всего активных дел: {total_items}\n"
                f"• Просрочено: {total_overdue}\n"
                f"• Процент просрочек: {overdue_percentage:.1f}%\n\n"
            )
            
            if overdue_percentage > 50:
                analysis_text += "🚨 <b>КРИТИЧЕСКИЙ УРОВЕНЬ!</b>\nТребуется немедленное вмешательство!"
            elif overdue_percentage > 25:
                analysis_text += "⚠️ <b>ВЫСОКИЙ УРОВЕНЬ!</b>\nНужно срочно исправлять!"
            elif overdue_percentage > 10:
                analysis_text += "🟡 <b>СРЕДНИЙ УРОВЕНЬ!</b>\nЕсть над чем работать!"
            else:
                analysis_text += "🟢 <b>НИЗКИЙ УРОВЕНЬ!</b>\nХорошо, но можно лучше!"
            
            await cb.message.edit_text(
                analysis_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к наказанию", callback_data="back_to_punishment")]
                ]),
                parse_mode="HTML"
            )
            
    except Exception as e:
        await cb.message.edit_text(
            "❌ <b>Ошибка анализа</b>\n\n"
            "Не удалось провести анализ.\n"
            "Попробуйте позже.",
            parse_mode="HTML"
        )
    
    await cb.answer()


@router.callback_query(F.data == "back_to_punishment")
async def back_to_punishment(cb: types.CallbackQuery) -> None:
    """Возврат к наказанию"""
    await cb.message.edit_text(
        "⚔️ <b>ВОЗВРАТ К НАКАЗАНИЮ</b>\n\n"
        "Используйте команду /arena_punishment для повторной проверки арены.",
        parse_mode="HTML"
    )
    await cb.answer()
