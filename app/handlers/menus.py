from __future__ import annotations

from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.keyboards.common import (
    main_menu,
    goals_menu,
    finance_menu,
    finance_upload_menu,
    finance_income_menu,
    finance_goals_menu,
    creditor_debtor_menu,
    health_menu,
    nutrition_menu,
    back_main_menu,
    goals_list_keyboard,
    books_menu,
)
from sqlalchemy import select
from app.db.session import session_scope
from app.db.models import User, Goal, GoalStatus
from app.services.exporters import export_user_data_to_excel
from pathlib import Path

router = Router()


@router.callback_query(F.data == "back_main")
async def back_main(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Главное меню:", reply_markup=main_menu())
    await cb.answer()


@router.callback_query(F.data == "menu_goals")
async def menu_goals(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Раздел целей:", reply_markup=goals_menu())
    await cb.answer()


@router.callback_query(F.data == "menu_books")
async def menu_books(cb: types.CallbackQuery) -> None:
    """Показать главное меню раздела книг"""
    await cb.message.edit_text(
        "📚 <b>Раздел книг</b>\n\n"
        "Здесь вы можете управлять своей библиотекой:\n"
        "• Добавлять книги для чтения\n"
        "• Отслеживать прогресс чтения\n"
        "• Сохранять цитаты и мысли\n"
        "• Получать советы от ИИ\n"
        "• Анализировать свои привычки чтения",
        reply_markup=books_menu(),
        parse_mode="HTML"
    )
    await cb.answer()





HELP_TEXT = (
    "Как работает бот:\n\n"
    "- Меню: выбери раздел — Цели, Финансы, Книги.\n"
    "- Все сообщения логируются для истории.\n"
    "- ИИ помогает формулировать SMART и мотивировать.\n\n"
    "Команды:\n"
    "/start — приветствие и меню\n"
    "/pillars — 7 опор характера\n"
    "/motivation — мотивационное сообщение\n"
    "/goal_add «текст» — добавить цель (ИИ)\n"
    "/goals — список активных целей\n"
    "/ab A | B — A/B-анализ с планом шагов\n"
    "/smart scope title | desc | YYYY-MM-DD — SMART-цель\n"
    "/expense 199.99 Категория описание — записать расход\n"
    "/finance_export — экспорт данных в Excel\n"
    "/meal breakfast Омлет [YYYY-MM-DD] — план питания\n"
    "/pomodoro — старт помодоро 25 минут\n\n"
    "Inline-кнопки:\n"
    "- В меню разделов используйте кнопки навигации.\n"
    "- В целях доступны кнопки завершить/отменить для каждого пункта.\n"
    "- В финансах — экспорт в Excel.\n"
    "- В книгах — управление библиотекой, цитаты, мысли, ИИ-советы.\n"
)


@router.callback_query(F.data == "help")
async def help_callback(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text(HELP_TEXT, reply_markup=back_main_menu(), parse_mode=None)
    await cb.answer()


@router.callback_query(F.data == "menu_finance")
async def menu_finance(cb: types.CallbackQuery) -> None:
    """Показать главное меню финансов с мини-отчетом"""
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    # Сначала показываем сообщение о том, что ИИ анализирует финансы
    await cb.message.edit_text(
        "🤖 <b>AI анализирует финансы...</b>\n\n"
        "Пожалуйста, подождите, пока ИИ проанализирует ваши данные и даст рекомендации.",
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Получить финансовые данные для отчета
        from app.services.finance_analytics import get_finance_summary
        summary = await get_finance_summary(session, db_user.id)
        
        # Получить совет от ИИ
        from app.services.llm import deepseek_complete
        try:
            ai_advice = await deepseek_complete(
                f"Дай краткий финансовый совет на основе данных: доходы {summary['monthly_income']}, расходы {summary['monthly_expenses']}, кредиторы {summary['total_creditors']}, должники {summary['total_debtors']}. Совет должен быть практичным и мотивирующим. Максимум 2-3 предложения.",
                system="Ты финансовый консультант. Дай краткий, практичный совет в 2-3 предложения.",
                max_tokens=100
            )
            # Заменить звездочки на HTML-теги для жирного текста
            import re
            ai_advice = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', ai_advice)
            
            # Ограничиваем длину совета и добавляем переносы строк
            if len(ai_advice) > 300:
                # Находим последнее полное предложение в пределах лимита
                truncated = ai_advice[:300]
                last_period = truncated.rfind('.')
                if last_period > 250:  # Если точка найдена в разумных пределах
                    ai_advice = truncated[:last_period + 1]
                else:
                    ai_advice = truncated + "..."
            
            # Добавляем переносы строк для лучшего форматирования
            ai_advice = ai_advice.replace(". ", ".\n")
            
            # Убираем лишние переносы строк в конце
            ai_advice = ai_advice.strip()
            
        except Exception:
            ai_advice = "Не удалось получить совет от ИИ"
        
        report_text = f"""💰 <b>Финансовый отчет</b>

💵 <b>Текущий месяц:</b>
📈 Доходы: {summary['monthly_income']:,.2f} ₽
📉 Расходы: {summary['monthly_expenses']:,.2f} ₽
💹 Баланс: {summary['monthly_balance']:,.2f} ₽

💸 <b>Кредиторы:</b> {summary['total_creditors']:,.2f} ₽
🏦 <b>Должники:</b> {summary['total_debtors']:,.2f} ₽

🤖 <b>Совет ИИ:</b>
{ai_advice}"""
        
        # Проверяем длину сообщения (Telegram ограничивает 4096 символов)
        if len(report_text) > 4000:
            # Если сообщение слишком длинное, разделяем его
            main_report = f"""💰 <b>Финансовый отчет</b>

💵 <b>Текущий месяц:</b>
📈 Доходы: {summary['monthly_income']:,.2f} ₽
📉 Расходы: {summary['monthly_expenses']:,.2f} ₽
💹 Баланс: {summary['monthly_balance']:,.2f} ₽

💸 <b>Кредиторы:</b> {summary['total_creditors']:,.2f} ₽
🏦 <b>Должники:</b> {summary['total_debtors']:,.2f} ₽"""

            # Отправляем основной отчет
            await cb.message.edit_text(main_report, reply_markup=finance_menu(), parse_mode="HTML")
            
            # Отправляем совет ИИ отдельным сообщением
            await cb.message.answer(
                f"🤖 <b>Совет ИИ:</b>\n\n{ai_advice}",
                parse_mode="HTML"
            )
        else:
            # Если сообщение помещается, отправляем всё вместе
            await cb.message.edit_text(report_text, reply_markup=finance_menu(), parse_mode="HTML")
        
        await cb.answer()


@router.callback_query(F.data == "menu_nutrition")
async def menu_nutrition(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Питание:", reply_markup=nutrition_menu())
    await cb.answer()


@router.callback_query(F.data == "menu_health")
async def menu_health(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text("Здоровье:", reply_markup=health_menu())
    await cb.answer()


@router.callback_query(F.data == "goals_list")
async def goals_list(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Получаем обычные цели
        goals = (
            await session.execute(select(Goal).where(Goal.user_id == db_user.id, Goal.status == GoalStatus.active))
        ).scalars().all()
        
        # Получаем финансовые цели
        from app.db.models import FinancialGoal
        financial_goals = (
            await session.execute(select(FinancialGoal).where(FinancialGoal.user_id == db_user.id, FinancialGoal.is_active.is_(True)))
        ).scalars().all()
        
        # Формируем общий список целей
        all_goals_text = "🎯 <b>Ваши цели:</b>\n\n"
        
        # Обычные цели
        if goals:
            all_goals_text += "📋 <b>Общие цели:</b>\n"
            for i, goal in enumerate(goals, 1):
                all_goals_text += f"{i}. {goal.title}\n"
            all_goals_text += "\n"
        
        # Финансовые цели
        if financial_goals:
            all_goals_text += "💰 <b>Финансовые цели:</b>\n"
            for i, goal in enumerate(financial_goals, 1):
                progress_percentage = (float(goal.current_amount) / float(goal.target_amount)) * 100
                remaining = float(goal.target_amount) - float(goal.current_amount)
                all_goals_text += f"{i}. {goal.name} - {progress_percentage:.1f}% ({goal.current_amount:,.0f}₽ / {goal.target_amount:,.0f}₽)\n"
                all_goals_text += f"   🎯 Осталось: {remaining:,.0f} ₽\n"
            all_goals_text += "\n"
        
        if not goals and not financial_goals:
            await cb.message.edit_text("Активных целей нет", reply_markup=goals_menu())
        else:
            # Создаем клавиатуру только для обычных целей (финансовые управляются отдельно)
            items = [(g.id, g.title) for g in goals]
            if items:
                await cb.message.edit_text(all_goals_text, reply_markup=goals_list_keyboard(items))
            else:
                await cb.message.edit_text(all_goals_text, reply_markup=goals_menu())
    
    await cb.answer()


@router.callback_query(F.data.startswith("goal_done:"))
async def goal_done(cb: types.CallbackQuery) -> None:
    goal_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        goal = await session.get(Goal, goal_id)
        if goal:
            goal.status = GoalStatus.completed
    await cb.answer("Готово ✅")
    await goals_list(cb)


@router.callback_query(F.data.startswith("goal_cancel:"))
async def goal_cancel(cb: types.CallbackQuery) -> None:
    goal_id = int(cb.data.split(":", 1)[1])
    async with session_scope() as session:
        goal = await session.get(Goal, goal_id)
        if goal:
            goal.status = GoalStatus.cancelled
    await cb.answer("Отменено ✖")
    await goals_list(cb)


@router.callback_query(F.data == "finance_export_cb")
async def finance_export_cb(cb: types.CallbackQuery) -> None:
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        out = Path("exports") / f"user_{db_user.id}.xlsx"
        await export_user_data_to_excel(session, db_user.id, out)
    try:
        await cb.message.answer_document(types.FSInputFile(out))  # type: ignore[arg-type]
    except Exception:
        await cb.message.answer("Файл экспортирован: " + str(out))
    await cb.answer()


@router.callback_query(F.data == "finance_goals")
async def finance_goals_menu_handler(cb: types.CallbackQuery) -> None:
    """Показать меню финансовых целей"""
    await cb.message.edit_text(
        "🎯 <b>Финансовые цели</b>\n\n"
        "Управляйте своими финансовыми целями и отслеживайте прогресс накоплений.",
        reply_markup=finance_goals_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "finance_upload_csv")
async def finance_upload_csv(cb: types.CallbackQuery) -> None:
    """Показать меню выбора банка для загрузки CSV"""
    await cb.message.edit_text(
        "📥 <b>Загрузка банковской выписки</b>\n\n"
        "Выберите банк, из которого загружаете выписку:",
        reply_markup=finance_upload_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data.startswith("bank_"))
async def bank_selection(cb: types.CallbackQuery) -> None:
    """Обработка выбора банка"""
    bank = cb.data.replace("bank_", "")
    bank_names = {
        "alpha": "Альфа-Банк",
        "tbank": "Т-Банк",
        "mbank": "MBank",
        "vtb": "ВТБ",
        "gazprom": "Газпромбанк"
    }
    
    bank_name = bank_names.get(bank, 'Банк')
    
    if bank == "mbank":
        message_text = (
            f"🏦 <b>{bank_name}</b>\n\n"
            "Отправьте XLS файл с банковской выпиской.\n"
            "Бот автоматически обработает и добавит транзакции.\n\n"
            "⚠️ <b>Особенности MBank:</b>\n"
            "• Поддерживает XLS формат\n"
            "• Учитывает расходы, доходы и переводы\n"
            "• Автоматически определяет категории"
        )
    else:
        message_text = (
            f"🏦 <b>{bank_name}</b>\n\n"
            "Отправьте CSV файл с банковской выпиской.\n"
            "Бот автоматически обработает и добавит транзакции в ваши расходы."
        )
    
    await cb.message.edit_text(
        message_text,
        reply_markup=back_main_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "finance_income")
async def finance_income(cb: types.CallbackQuery) -> None:
    """Показать меню доходов"""
    await cb.message.edit_text(
        "💰 <b>Управление доходами</b>\n\n"
        "Выберите действие:",
        reply_markup=finance_income_menu(),
        parse_mode="HTML"
    )
    await cb.answer()


@router.callback_query(F.data == "finance_creditors")
async def finance_creditors(cb: types.CallbackQuery) -> None:
    """Показать список кредиторов"""
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Получить кредиторов
        from app.services.finance_analytics import get_creditors
        creditors = await get_creditors(session, db_user.id)
        
        if not creditors:
            await cb.message.edit_text(
                "💸 <b>Кредиторы</b>\n\n"
                "У вас пока нет кредиторов.\n"
                "Нажмите кнопку ниже, чтобы добавить первого.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить кредитора", callback_data="creditor_add")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")]
                ]),
                parse_mode="HTML"
            )
        else:
            text = "💸 <b>Ваши кредиторы:</b>\n\n"
            for creditor in creditors:
                text += f"👤 <b>{creditor['name']}</b>\n"
                text += f"💰 Сумма: {creditor['amount']:,.2f} ₽\n"
                text += f"📅 Срок: {creditor['due_date']}\n\n"
            
            # Создать клавиатуру со списком кредиторов
            keyboard = []
            for creditor in creditors:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"👤 {creditor['name']} - {creditor['amount']:,.0f}₽",
                        callback_data=f"creditor_view:{creditor['id']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton(text="➕ Добавить кредитора", callback_data="creditor_add")])
            keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")])
            
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    
    await cb.answer()


@router.callback_query(F.data == "finance_debtors")
async def finance_debtors(cb: types.CallbackQuery) -> None:
    """Показать список должников"""
    user = cb.from_user
    if not user:
        await cb.answer()
        return
    
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        
        # Получить должников
        from app.services.finance_analytics import get_debtors
        debtors = await get_debtors(session, db_user.id)
        
        if not debtors:
            await cb.message.edit_text(
                "🏦 <b>Должники</b>\n\n"
                "У вас пока нет должников.\n"
                "Нажмите кнопку ниже, чтобы добавить первого.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить должника", callback_data="debtor_add")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")]
                ]),
                parse_mode="HTML"
            )
        else:
            text = "🏦 <b>Ваши должники:</b>\n\n"
            for debtor in debtors:
                text += f"👤 <b>{debtor['name']}</b>\n"
                text += f"💰 Сумма: {debtor['amount']:,.2f} ₽\n"
                text += f"📅 Срок: {debtor['due_date']}\n\n"
            
            # Создать клавиатуру со списком должников
            keyboard = []
            for debtor in debtors:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"👤 {debtor['name']} - {debtor['amount']:,.0f}₽",
                        callback_data=f"debtor_view:{debtor['id']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton(text="➕ Добавить должника", callback_data="debtor_add")])
            keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_finance")])
            
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    
    await cb.answer()


