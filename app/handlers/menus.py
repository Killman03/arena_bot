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
    "🤖 <b>Gladiator Arena Life Bot</b>\n\n"
    "Ваш персональный ментор для построения характера победителя!\n\n"
    "🎯 <b>Основные разделы:</b>\n"
    "• <b>Цели</b> - SMART-цели с ИИ-помощником\n"
    "• <b>Финансы</b> - учет доходов/расходов, экспорт в Excel\n"
    "• <b>Книги</b> - библиотека, цитаты, мысли, ИИ-анализ\n"
    "• <b>Здоровье</b> - трекинг показателей, импорт данных\n"
    "• <b>Питание</b> - планы готовки, сушка/масса\n"
    "• <b>Челленджи</b> - временные вызовы и цели\n"
    "• <b>Мотивация</b> - видение, миссия, ценности\n"
    "• <b>Анализ</b> - еженедельная ретроспектива\n"
    "• <b>To-Do</b> - задачи и ежедневные дела\n\n"
    "💡 <b>ИИ-функции:</b>\n"
    "• Формулирование SMART-целей\n"
    "• A/B анализ с планом действий\n"
    "• Анализ трендов здоровья\n"
    "• Планы готовки и списки покупок\n"
    "• Мотивационные сообщения\n\n"
    "📱 <b>Команды:</b>\n"
    "/start — главное меню\n"
    "/pillars — 7 опор характера\n"
    "/motivation — мотивация\n"
    "/goal_add «текст» — добавить цель\n"
    "/goals — список целей\n"
    "/ab A | B — A/B анализ\n"
    "/expense 199.99 Категория описание — расход\n"
    "/finance_export — экспорт в Excel\n"
    "/meal breakfast Омлет [YYYY-MM-DD] — питание\n"
    "/pomodoro — помодоро таймер\n\n"
    "❓ <b>Нужна помощь?</b>\n"
    "В каждом разделе есть кнопка «❓ Помощь» с подробными инструкциями!"
)


@router.callback_query(F.data == "help")
async def help_callback(cb: types.CallbackQuery) -> None:
    await cb.message.edit_text(HELP_TEXT, reply_markup=back_main_menu(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "guide")
async def guide_callback(cb: types.CallbackQuery) -> None:
    guide_text = (
        "📚 <b>Полное руководство пользователя</b>\n\n"
        "🎯 <b>1. ЦЕЛИ</b>\n"
        "• Создавайте SMART-цели с помощью ИИ\n"
        "• Используйте A/B анализ для планирования\n"
        "• Отслеживайте прогресс и завершение\n\n"
        "💰 <b>2. ФИНАНСЫ</b>\n"
        "• Записывайте доходы и расходы\n"
        "• Категоризируйте транзакции\n"
        "• Экспортируйте данные в Excel\n"
        "• Загружайте данные из банковских приложений\n\n"
        "📚 <b>3. КНИГИ</b>\n"
        "• Ведите библиотеку прочитанных книг\n"
        "• Сохраняйте цитаты и мысли\n"
        "• Получайте ИИ-анализ книг\n"
        "• Отслеживайте прогресс чтения\n\n"
        "🩺 <b>4. ЗДОРОВЬЕ</b>\n"
        "• Трекинг показателей (шаги, сон, вес)\n"
        "• Импорт данных из приложений здоровья\n"
        "• Аналитика трендов с ИИ\n"
        "• Настраиваемые напоминания\n\n"
        "🍽️ <b>5. ПИТАНИЕ</b>\n"
        "• Планы готовки на 3 дня\n"
        "• Списки покупок от ИИ\n"
        "• Цели по калориям (сушка/масса)\n"
        "• Автоматические напоминания\n\n"
        "🏆 <b>6. ЧЕЛЛЕНДЖИ</b>\n"
        "• Создавайте временные вызовы\n"
        "• Отслеживайте прогресс\n"
        "• Мотивационные сообщения\n\n"
        "🔥 <b>7. МОТИВАЦИЯ</b>\n"
        "• Формулируйте видение и миссию\n"
        "• Определяйте личные ценности\n"
        "• Ставьте годовые цели\n\n"
        "📊 <b>8. АНАЛИЗ</b>\n"
        "• Еженедельная ретроспектива\n"
        "• ИИ-анализ прогресса\n"
        "• История анализов\n\n"
        "📝 <b>9. TO-DO</b>\n"
        "• Создавайте задачи\n"
        "• Настраивайте приоритеты\n"
        "• Ежедневные дела\n\n"
        "⚙️ <b>10. НАСТРОЙКИ</b>\n"
        "• Часовой пояс\n"
        "• Персональные настройки\n\n"
        "💡 <b>Советы:</b>\n"
        "• Используйте кнопку «❓ Помощь» в каждом разделе\n"
        "• ИИ поможет с формулировкой целей и анализом\n"
        "• Регулярно проводите анализ недели\n"
        "• Импортируйте данные здоровья для лучшей аналитики"
    )
    
    await cb.message.edit_text(guide_text, reply_markup=back_main_menu(), parse_mode="HTML")
    await cb.answer()


# ==================== ПОМОЩЬ ПО РАЗДЕЛАМ ====================

@router.callback_query(F.data == "goals_help")
async def goals_help(cb: types.CallbackQuery) -> None:
    help_text = (
        "🎯 <b>Раздел ЦЕЛИ - Помощь</b>\n\n"
        "📋 <b>Что можно делать:</b>\n"
        "• Создавать SMART-цели с помощью ИИ\n"
        "• Использовать A/B анализ для планирования\n"
        "• Отслеживать прогресс и завершение\n"
        "• Просматривать список активных целей\n"
        "• Редактировать существующие цели\n\n"
        "💡 <b>SMART-цели:</b>\n"
        "• <b>S</b>pecific (Конкретная) - четко сформулированная\n"
        "• <b>M</b>easurable (Измеримая) - с конкретными показателями\n"
        "• <b>A</b>chievable (Достижимая) - реалистичная\n"
        "• <b>R</b>elevant (Релевантная) - важная для вас\n"
        "• <b>T</b>ime-bound (Ограниченная по времени) - с дедлайном\n\n"
        "🔧 <b>Как использовать:</b>\n"
        "1. Нажмите «➕ Добавить цель»\n"
        "2. Введите описание цели\n"
        "3. ИИ автоматически сформулирует SMART-описание\n"
        "4. Отслеживайте прогресс\n\n"
        "📱 <b>Команды:</b>\n"
        "/goal_add «текст» - добавить цель\n"
        "/goals - список целей\n"
        "/ab A | B - A/B анализ\n"
        "/smart scope title | desc | YYYY-MM-DD - SMART-цель"
    )
    
    await cb.message.edit_text(help_text, reply_markup=back_main_menu(), parse_mode="HTML")
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


@router.callback_query(F.data == "finance_help")
async def finance_help(cb: types.CallbackQuery) -> None:
    help_text = (
        "💰 <b>Раздел ФИНАНСЫ - Помощь</b>\n\n"
        "📋 <b>Что можно делать:</b>\n"
        "• Записывать доходы и расходы\n"
        "• Категоризировать транзакции\n"
        "• Экспортировать данные в Excel\n"
        "• Загружать данные из банковских приложений\n"
        "• Вести учет кредиторов и должников\n"
        "• Ставить финансовые цели\n\n"
        "🔧 <b>Как использовать:</b>\n"
        "1. <b>Добавить расход:</b> Нажмите «➕ Добавить расход»\n"
        "2. <b>Выберите категорию:</b> Покупки, питание, транспорт и др.\n"
        "3. <b>Введите сумму и описание</b>\n"
        "4. <b>Экспорт:</b> Нажмите «📊 Экспорт Excel» для выгрузки\n\n"
        "📱 <b>Команды:</b>\n"
        "/expense 199.99 Категория описание - записать расход\n"
        "/finance_export - экспорт в Excel\n\n"
        "🏦 <b>Поддерживаемые банки:</b>\n"
        "• Альфа-Банк\n"
        "• Т-Банк\n"
        "• MBank\n\n"
        "💡 <b>Советы:</b>\n"
        "• Регулярно записывайте все траты\n"
        "• Используйте категории для анализа\n"
        "• Экспортируйте данные ежемесячно"
    )
    
    await cb.message.edit_text(help_text, reply_markup=back_main_menu(), parse_mode="HTML")
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


@router.callback_query(F.data == "challenges_help")
async def challenges_help(cb: types.CallbackQuery) -> None:
    help_text = (
        "🏆 <b>Раздел ЧЕЛЛЕНДЖИ - Помощь</b>\n\n"
        "📋 <b>Что можно делать:</b>\n"
        "• Создавать временные вызовы\n"
        "• Отслеживать прогресс выполнения\n"
        "• Устанавливать дедлайны\n"
        "• Отмечать выполненные челленджи\n\n"
        "🔧 <b>Как использовать:</b>\n"
        "1. Нажмите «➕ Добавить» для создания челленджа\n"
        "2. Введите название и описание\n"
        "3. Установите дату окончания\n"
        "4. Отслеживайте прогресс\n"
        "5. Отметьте как выполненный по завершении\n\n"
        "💡 <b>Примеры челленджей:</b>\n"
        "• 30 дней без сахара\n"
        "• 21 день медитации\n"
        "• 7 дней раннего подъема\n"
        "• Месяц без покупок\n\n"
        "📱 <b>Управление:</b>\n"
        "• Изменение текста и дат\n"
        "• Активация/деактивация\n"
        "• Просмотр списка активных"
    )
    
    await cb.message.edit_text(help_text, reply_markup=back_main_menu(), parse_mode="HTML")
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


@router.callback_query(F.data == "motivation_help")
async def motivation_help(cb: types.CallbackQuery) -> None:
    help_text = (
        "🔥 <b>Раздел МОТИВАЦИЯ - Помощь</b>\n\n"
        "📋 <b>Что можно делать:</b>\n"
        "• Формулировать личное видение\n"
        "• Определять миссию жизни\n"
        "• Ставить годовые цели\n"
        "• Выявлять ключевые ценности\n"
        "• Получать мотивационные сообщения\n\n"
        "🔧 <b>Как использовать:</b>\n"
        "1. <b>Видение:</b> Опишите, кем хотите стать\n"
        "2. <b>Миссия:</b> Определите свою цель в жизни\n"
        "3. <b>Ценности:</b> Выберите 3-5 ключевых принципов\n"
        "4. <b>Годовая цель:</b> Поставьте главную цель года\n\n"
        "💡 <b>Советы по формулировке:</b>\n"
        "• <b>Видение:</b> «Я - успешный предприниматель, который...»\n"
        "• <b>Миссия:</b> «Моя цель - помогать людям...»\n"
        "• <b>Ценности:</b> Честность, ответственность, рост\n\n"
        "📱 <b>Команды:</b>\n"
        "/motivation - получить мотивационное сообщение\n"
        "/pillars - 7 опор характера\n\n"
        "🔄 <b>Регулярность:</b>\n"
        "• Пересматривайте видение ежемесячно\n"
        "• Обновляйте миссию при изменении приоритетов\n"
        "• Используйте ценности для принятия решений"
    )
    
    await cb.message.edit_text(help_text, reply_markup=back_main_menu(), parse_mode="HTML")
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


