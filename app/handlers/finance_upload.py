from __future__ import annotations

import csv
from io import StringIO
from datetime import datetime
from decimal import Decimal

from aiogram import Router, types, F
from aiogram.filters import Command
from sqlalchemy import select

from app.db.session import session_scope
from app.db.models import FinanceTransaction, User
from app.services.finance_analytics import process_bank_csv

router = Router()


@router.message(Command("finance_upload"))
async def finance_upload(message: types.Message) -> None:
    """Отправьте CSV-файл как ответ на это сообщение. Ожидаемые колонки: date,amount,category,description"""
    await message.answer("Пришлите CSV-файл банковской выписки ответом на это сообщение.")


@router.message(lambda m: m.document and m.document.mime_type == "text/csv")
async def handle_csv_upload(message: types.Message, bot: types.Bot) -> None:
    """Обрабатывает загруженный CSV файл"""
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    try:
        # Получить файл
        file = await bot.get_file(message.document.file_id)
        content = await bot.download_file(file.file_path)
        csv_text = content.read().decode("utf-8")
        
        # Определить тип банка по содержимому файла
        bank_type = detect_bank_type(csv_text)
        
        # Если это Т-Банк, используем специальную обработку
        if bank_type == "Т-Банк":
            csv_text = fix_tbank_csv_format(csv_text)
        
        async with session_scope() as session:
            db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
            
            # Обработать CSV через сервис
            result = await process_bank_csv(session, db_user.id, csv_text, bank_type)
            
            if result["processed"] > 0:
                await message.answer(
                    f"✅ <b>CSV файл обработан!</b>\n\n"
                    f"📊 <b>Результат:</b>\n"
                    f"📥 Обработано строк: {result['processed']}\n"
                    f"➕ Добавлено транзакций: {result['added']}\n"
                    f"⏭️ Пропущено: {result['skipped']}\n"
                    f"🏦 Определен банк: {bank_type}",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"⚠️ <b>Файл обработан, но транзакции не добавлены</b>\n\n"
                    f"📊 <b>Результат:</b>\n"
                    f"📥 Обработано строк: {result['processed']}\n"
                    f"❌ Ошибки: {len(result['errors'])}\n"
                    f"🏦 Определен банк: {bank_type}",
                    parse_mode="HTML"
                )
                
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка при обработке файла:</b>\n{str(e)}", parse_mode="HTML")


def detect_bank_type(csv_content: str) -> str:
    """Определить тип банка по содержимому CSV"""
    try:
        # Сначала пробуем стандартный CSV парсер
        try:
            reader = csv.DictReader(StringIO(csv_content))
            headers = reader.fieldnames or []
        except:
            # Если не получилось, пробуем ручное разбиение по первой строке
            lines = csv_content.strip().split('\n')
            if lines:
                # Берем первую строку и разбиваем по запятой или точке с запятой
                header_line = lines[0]
                if ';' in header_line:
                    # Если есть точки с запятой, разбиваем по ним
                    headers = [h.strip().strip('"') for h in header_line.split(';')]
                else:
                    # Иначе по запятой
                    headers = [h.strip().strip('"') for h in header_line.split(',')]
            else:
                headers = []
        
        # Приводим заголовки к нижнему регистру для сравнения
        headers_lower = [h.lower() if h else "" for h in headers]
        
        print(f"DEBUG: Заголовки CSV: {headers}")  # Отладочная информация
        
        # Создаем словарь с уникальными идентификаторами для каждого банка
        bank_identifiers = {
            "Альфа-Банк": [
                ["operationdate", "transactiondate", "accountname", "cardname", "merchant", "bonusvalue"],  # Уникальные для Альфа-Банка
                ["operationdate", "transactiondate"]
            ],

            "Т-Банк": [
                ["mcc", "кэшбэк", "бонусы", "инвесткопилка"],  # Уникальные для Т-Банка
                ["дата операции", "дата платежа"]
            ],

            "MBank": [
                ["получатель/плательщик", "расход", "приход", "операция"],  # Уникальные для MBank
                ["дата", "получатель/плательщик"]
            ],

        }
        
        # Проверяем каждый банк по уникальным идентификаторам
        for bank_name, identifier_groups in bank_identifiers.items():
            # Для каждого банка нужно найти хотя бы одну группу уникальных идентификаторов
            for identifier_group in identifier_groups:
                if all(any(identifier in h for h in headers_lower) for identifier in identifier_group):
                    print(f"DEBUG: Определен банк {bank_name} по идентификаторам: {identifier_group}")
                    return bank_name
        
        # Если не удалось определить по уникальным идентификаторам, используем общие правила
        print("DEBUG: Не удалось определить по уникальным идентификаторам, используем общие правила")
        
        # Универсальные заголовки (английские)
        if any("date" in h for h in headers_lower) and any("amount" in h for h in headers_lower):
            return "Универсальный"
        
        # Универсальные заголовки (русские)
        if any("дата" in h for h in headers_lower) and any("сумма" in h for h in headers_lower):
            return "Универсальный"
        
        # Если есть хотя бы дата и сумма - считаем универсальным
        if any("дата" in h for h in headers_lower) and any("сумма" in h for h in headers_lower):
            return "Универсальный"
        
        print("DEBUG: Банк не определен, возвращаем 'Неизвестный банк'")
        return "Неизвестный банк"
        
    except Exception as e:
        print(f"DEBUG: Ошибка определения банка: {e}")
        return "Неизвестный банк"


def fix_tbank_csv_format(csv_content: str) -> str:
    """Исправляет формат CSV Т-Банка (убирает лишние кавычки и точки с запятой)"""
    try:
        print("DEBUG: Начинаю исправление формата Т-Банка")
        
        # Разбиваем на строки
        lines = csv_content.strip().split('\n')
        
        # Обрабатываем заголовки
        if lines:
            # Убираем лишние кавычки и точки с запятой из заголовков
            header_line = lines[0]
            print(f"DEBUG: Исходная строка заголовков: {header_line}")
            
            # Заменяем "Дата операции;"Дата платежа";... на правильный формат
            header_line = header_line.replace('";"', '","').replace('";', '",')
            if header_line.startswith('"'):
                header_line = header_line[1:]
            if header_line.endswith('"'):
                header_line = header_line[:-1]
            
            # Разбиваем заголовки по запятой
            headers = [h.strip().strip('"') for h in header_line.split(',')]
            
            # Создаем новую первую строку
            lines[0] = ','.join(headers)
            print(f"DEBUG: Исправленные заголовки: {lines[0]}")
        
        # Обрабатываем данные
        fixed_lines = [lines[0]]  # Добавляем исправленные заголовки
        
        for i, line in enumerate(lines[1:], 1):
            if line.strip():
                print(f"DEBUG: Обрабатываю строку {i}: {line[:100]}...")
                
                # Убираем лишние кавычки и точки с запятой
                line = line.replace('";"', '","').replace('";', '",')
                if line.startswith('"'):
                    line = line[1:]
                if line.endswith('"'):
                    line = line[:-1]
                
                # Разбиваем по запятой и убираем лишние кавычки
                parts = [part.strip().strip('"') for part in line.split(',')]
                
                # Проверяем, что количество частей соответствует заголовкам
                if len(parts) == len(headers):
                    fixed_lines.append(','.join(parts))
                    print(f"DEBUG: Строка {i} исправлена, частей: {len(parts)}")
                else:
                    print(f"DEBUG: Строка {i} пропущена - несоответствие количества частей: {len(parts)} != {len(headers)}")
                    # Пробуем альтернативный способ разбиения
                    if ';' in line:
                        parts_alt = [part.strip().strip('"') for part in line.split(';')]
                        if len(parts_alt) == len(headers):
                            fixed_lines.append(','.join(parts_alt))
                            print(f"DEBUG: Строка {i} исправлена альтернативным способом")
                        else:
                            print(f"DEBUG: Строка {i} не может быть исправлена")
        
        result = '\n'.join(fixed_lines)
        print(f"DEBUG: Исправление завершено. Строк: {len(fixed_lines)}")
        print(f"DEBUG: Пример исправленной строки: {fixed_lines[1] if len(fixed_lines) > 1 else 'Нет данных'}")
        
        return result
        
    except Exception as e:
        print(f"DEBUG: Ошибка исправления формата Т-Банка: {e}")
        return csv_content


# Старый обработчик для обратной совместимости
@router.message(lambda m: m.document and (m.caption or "").startswith("#finance"))
async def handle_bank_csv_legacy(message: types.Message, bot: types.Bot) -> None:
    """Парсит CSV, импортирует транзакции. Используйте caption: #finance"""
    user = message.from_user
    if not user:
        return
    file = await bot.get_file(message.document.file_id)
    content = await bot.download_file(file.file_path)
    text = content.read().decode("utf-8")
    reader = csv.DictReader(StringIO(text))
    rows = list(reader)
    count = 0
    async with session_scope() as session:
        db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
        for r in rows:
            try:
                dt = datetime.fromisoformat(r["date"]).date()
                amount = float(r["amount"])
                category = r.get("category", "Прочее") or "Прочее"
                description = r.get("description")
            except Exception:
                continue
            session.add(
                FinanceTransaction(
                    user_id=db_user.id,
                    date=dt,
                    amount=amount,
                    category=category,
                    description=description,
                )
            )
            count += 1
    await message.answer(f"Импортировано записей: {count}")


# ===== ОБРАБОТЧИК ДЛЯ EXCEL ФАЙЛОВ =====

@router.message(lambda m: m.document and m.document.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
async def handle_excel_upload(message: types.Message, bot: types.Bot) -> None:
    """Обрабатывает загруженный Excel файл для обновления данных"""
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    # Проверяем, не является ли это файлом MBank
    try:
        # Получить файл для проверки содержимого
        file = await bot.get_file(message.document.file_id)
        content = await bot.download_file(file.file_path)
        
        # Сохраняем временный файл для проверки
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            temp_file.write(content.read())
            temp_file_path = temp_file.name
        
        try:
            # Пробуем прочитать как MBank файл (пропускаем первые 12 строк)
            import pandas as pd
            df = pd.read_excel(temp_file_path, skiprows=12, engine='openpyxl')
            
            # Проверяем, есть ли колонки MBank
            mbank_columns = ["Дата", "Получатель/Плательщик", "Расход", "Приход", "Операция"]
            if all(col in df.columns for col in mbank_columns):
                # Это файл MBank в XLSX формате
                await message.answer(
                    "🔍 <b>Обнаружен файл MBank в XLSX формате!</b>\n\n"
                    "Обрабатываю как выписку MBank...",
                    parse_mode="HTML"
                )
                
                # Конвертируем в CSV и обрабатываем как MBank
                csv_content = df.to_csv(index=False, sep=',')
                
                async with session_scope() as session:
                    db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
                    
                    # Обрабатываем как MBank CSV
                    from app.services.finance_analytics import process_bank_csv
                    
                    result = await process_bank_csv(session, db_user.id, csv_content, "MBank")
                    
                    # Формируем отчет об импорте
                    if result["processed"] > 0:
                        await message.answer(
                            f"✅ <b>XLSX файл MBank обработан!</b>\n\n"
                            f"📊 <b>Результат:</b>\n"
                            f"📥 Обработано строк: {result['processed']}\n"
                            f"➕ Добавлено транзакций: {result['added']}\n"
                            f"⏭️ Пропущено: {result['skipped']}\n"
                            f"🏦 Банк: MBank",
                            parse_mode="HTML"
                        )
                    else:
                        await message.answer(
                            f"⚠️ <b>XLSX файл обработан, но транзакции не добавлены</b>\n\n"
                            f"📊 <b>Результат:</b>\n"
                            f"📥 Обработано строк: {result['processed']}\n"
                            f"❌ Ошибки: {len(result['errors'])}\n"
                            f"🏦 Банк: MBank",
                            parse_mode="HTML"
                        )
                
                # Удаляем временный файл и выходим
                os.unlink(temp_file_path)
                return
                
        except Exception:
            # Если не удалось прочитать как MBank, продолжаем стандартную обработку Excel
            pass
        finally:
            # Удаляем временный файл
            os.unlink(temp_file_path)
            
        # Сбрасываем указатель файла для повторного чтения
        content.seek(0)
        
    except Exception as e:
        # Если не удалось проверить файл, продолжаем стандартную обработку
        pass
    
    try:
        # Получить файл
        file = await bot.get_file(message.document.file_id)
        content = await bot.download_file(file.file_path)
        
        # Сохраняем временный файл
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            temp_file.write(content.read())
            temp_file_path = temp_file.name
        
        try:
            async with session_scope() as session:
                db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
                
                # Импортируем Excel через сервис
                from app.services.excel_importer import import_excel_data
                from pathlib import Path
                
                result = await import_excel_data(session, db_user.id, Path(temp_file_path))
                
                # Формируем отчет об импорте
                if result["errors"]:
                    error_text = f"⚠️ <b>Excel файл обработан с ошибками!</b>\n\n"
                    error_text += f"📊 <b>Результат:</b>\n"
                    error_text += f"✅ Обновлено записей: {result['updated']}\n"
                    error_text += f"➕ Создано новых: {result['created']}\n"
                    error_text += f"🗑️ Удалено записей: {result['deleted']}\n"
                    error_text += f"❌ Ошибки: {len(result['errors'])}\n\n"
                    error_text += f"<b>Детали ошибок:</b>\n"
                    for error in result["errors"][:5]:  # Показываем первые 5 ошибок
                        error_text += f"• {error}\n"
                    if len(result["errors"]) > 5:
                        error_text += f"... и еще {len(result['errors']) - 5} ошибок"
                    
                    await message.answer(error_text, parse_mode="HTML")
                else:
                    success_text = f"✅ <b>Excel файл успешно обработан!</b>\n\n"
                    success_text += f"📊 <b>Результат:</b>\n"
                    success_text += f"✅ Обновлено записей: {result['updated']}\n"
                    success_text += f"➕ Создано новых: {result['created']}\n"
                    success_text += f"🗑️ Удалено записей: {result['deleted']}\n"
                    success_text += f"🎯 Все изменения внесены в базу данных"
                    
                    await message.answer(success_text, parse_mode="HTML")
                
        finally:
            # Удаляем временный файл
            os.unlink(temp_file_path)
                
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при обработке Excel файла:</b>\n{str(e)}", 
            parse_mode="HTML"
        )


# ===== ОБРАБОТЧИК ДЛЯ XLS ФАЙЛОВ MBANK =====

@router.message(lambda m: m.document and m.document.mime_type == "application/vnd.ms-excel")
async def handle_xls_upload(message: types.Message, bot: types.Bot) -> None:
    """Обрабатывает загруженный XLS файл MBank"""
    user = message.from_user
    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        return
    
    # Проверяем наличие необходимых библиотек
    try:
        import pandas as pd
        import xlrd
    except ImportError as e:
        if "xlrd" in str(e):
            await message.answer(
                "❌ <b>Отсутствует необходимая библиотека!</b>\n\n"
                "Для работы с XLS файлами MBank необходимо установить библиотеку xlrd:\n\n"
                "```bash\npip install xlrd>=2.0.1\n```\n\n"
                "Или используйте команду:\n"
                "```bash\npip install -r requirements.txt\n```\n\n"
                "После установки перезапустите бота.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ <b>Ошибка импорта библиотек!</b>\n\n"
                f"Детали ошибки: {str(e)}\n\n"
                "Убедитесь, что все зависимости установлены корректно.",
                parse_mode="HTML"
            )
        return
    
    try:
        # Получить файл
        file = await bot.get_file(message.document.file_id)
        content = await bot.download_file(file.file_path)
        
        # Сохраняем временный файл
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xls') as temp_file:
            temp_file.write(content.read())
            temp_file_path = temp_file.name
        
        try:
            # Читаем XLS файл
            import pandas as pd
            
            try:
                # Пропускаем первые 12 строк (шапка и ненужная информация)
                df = pd.read_excel(temp_file_path, skiprows=12, engine='xlrd')
            except ImportError:
                # Если xlrd не установлен, пробуем openpyxl
                try:
                    df = pd.read_excel(temp_file_path, skiprows=12, engine='openpyxl')
                except Exception as e:
                    await message.answer(
                        "❌ <b>Ошибка чтения XLS файла!</b>\n\n"
                        "Для работы с XLS файлами MBank необходимо установить библиотеку xlrd:\n\n"
                        "```bash\npip install xlrd>=2.0.1\n```\n\n"
                        "Или используйте команду:\n"
                        "```bash\npip install -r requirements.txt\n```",
                        parse_mode="HTML"
                    )
                    return
            except Exception as e:
                await message.answer(
                    f"❌ <b>Ошибка чтения XLS файла!</b>\n\n"
                    f"Детали ошибки: {str(e)}\n\n"
                    "Убедитесь, что файл не поврежден и имеет правильный формат.",
                    parse_mode="HTML"
                )
                return
            
            # Проверяем, что есть нужные колонки
            required_columns = ["Дата", "Получатель/Плательщик", "Расход", "Приход", "Операция"]
            if not all(col in df.columns for col in required_columns):
                await message.answer(
                    "❌ <b>Неверный формат XLS файла!</b>\n\n"
                    "Ожидаемые колонки:\n"
                    "• Дата\n"
                    "• Получатель/Плательщик\n"
                    "• Расход\n"
                    "• Приход\n"
                    "• Операция\n\n"
                    "Убедитесь, что загружаете файл от MBank.",
                    parse_mode="HTML"
                )
                return
            
            # Конвертируем в CSV формат для обработки
            csv_content = df.to_csv(index=False, sep=',')
            
            async with session_scope() as session:
                db_user = (await session.execute(select(User).where(User.telegram_id == user.id))).scalar_one()
                
                # Обрабатываем как MBank CSV
                from app.services.finance_analytics import process_bank_csv
                
                result = await process_bank_csv(session, db_user.id, csv_content, "MBank")
                
                # Формируем отчет об импорте
                if result["processed"] > 0:
                    await message.answer(
                        f"✅ <b>XLS файл MBank обработан!</b>\n\n"
                        f"📊 <b>Результат:</b>\n"
                        f"📥 Обработано строк: {result['processed']}\n"
                        f"➕ Добавлено транзакций: {result['added']}\n"
                        f"⏭️ Пропущено: {result['skipped']}\n"
                        f"🏦 Банк: MBank",
                        parse_mode="HTML"
                    )
                else:
                    await message.answer(
                        f"⚠️ <b>XLS файл обработан, но транзакции не добавлены</b>\n\n"
                        f"📊 <b>Результат:</b>\n"
                        f"📥 Обработано строк: {result['processed']}\n"
                        f"❌ Ошибки: {len(result['errors'])}\n"
                        f"🏦 Банк: MBank",
                        parse_mode="HTML"
                    )
                
        finally:
            # Удаляем временный файл
            os.unlink(temp_file_path)
                
    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при обработке XLS файла:</b>\n{str(e)}", 
            parse_mode="HTML"
        )






