#!/usr/bin/env python3
"""
Сервис для импорта данных здоровья из ZIP файлов.
Пользователь загружает ZIP файл, бот извлекает .db файл и импортирует данные.
"""

import zipfile
import sqlite3
import tempfile
import os
from datetime import datetime, date
from typing import Dict, List, Any, Optional
import logging

from app.db.models.health import HealthMetric
from app.db.session import session_scope
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ZipImporterService:
    """Сервис для импорта данных здоровья из ZIP файлов."""
    
    def __init__(self):
        self.supported_formats = ['.zip']
        self.db_extensions = ['.db', '.sqlite', '.sqlite3']
    
    async def import_health_data_from_zip(
        self, 
        session, 
        user_id: int, 
        zip_file_path: str
    ) -> Dict[str, Any]:
        """
        Импортирует данные здоровья из ZIP файла.
        
        Args:
            session: Сессия базы данных
            user_id: ID пользователя
            zip_file_path: Путь к ZIP файлу
            
        Returns:
            Dict с результатом импорта
        """
        try:
            # Проверяем, что это ZIP файл
            if not zip_file_path.lower().endswith('.zip'):
                return {
                    'success': False,
                    'error': 'Файл должен быть в формате .zip'
                }
            
            # Создаем временную директорию для извлечения
            with tempfile.TemporaryDirectory() as temp_dir:
                # Извлекаем ZIP файл
                extracted_files = self._extract_zip(zip_file_path, temp_dir)
                
                if not extracted_files:
                    return {
                        'success': False,
                        'error': 'ZIP файл пуст или поврежден'
                    }
                
                # Ищем .db файл
                db_file = self._find_db_file(extracted_files)
                
                if not db_file:
                    return {
                        'success': False,
                        'error': 'В ZIP файле не найден файл базы данных (.db, .sqlite)'
                    }
                
                # Импортируем данные из .db файла
                import_result = await self._import_from_db_file(
                    session, user_id, db_file
                )
                
                return import_result
                
        except Exception as e:
            logger.error(f"Ошибка импорта ZIP файла: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Ошибка импорта: {str(e)}'
            }
    
    def _extract_zip(self, zip_path: str, extract_dir: str) -> List[str]:
        """Извлекает ZIP файл во временную директорию."""
        extracted_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                
                # Получаем список извлеченных файлов
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        extracted_files.append(file_path)
                        
        except zipfile.BadZipFile:
            raise ValueError("ZIP файл поврежден или имеет неправильный формат")
        
        return extracted_files
    
    def _find_db_file(self, file_paths: List[str]) -> Optional[str]:
        """Ищет файл базы данных среди извлеченных файлов."""
        for file_path in file_paths:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in self.db_extensions:
                return file_path
        return None
    
    async def _import_from_db_file(
        self, 
        session, 
        user_id: int, 
        db_file_path: str
    ) -> Dict[str, Any]:
        """Импортирует данные из SQLite файла."""
        try:
            # Подключаемся к SQLite файлу
            sqlite_conn = sqlite3.connect(db_file_path)
            sqlite_cursor = sqlite_conn.cursor()
            
            # Получаем список таблиц
            sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = sqlite_cursor.fetchall()
            
            imported_data = {}
            total_records = 0
            
            # Импортируем данные из каждой таблицы
            for table in tables:
                table_name = table[0]
                
                # Пропускаем системные таблицы
                if table_name.startswith('sqlite_'):
                    continue
                
                # Получаем структуру таблицы
                sqlite_cursor.execute(f"PRAGMA table_info({table_name});")
                columns = sqlite_cursor.fetchall()
                
                # Получаем данные
                sqlite_cursor.execute(f"SELECT * FROM {table_name};")
                rows = sqlite_cursor.fetchall()
                
                if rows:
                    imported_data[table_name] = {
                        'columns': [col[1] for col in columns],
                        'rows': rows,
                        'count': len(rows)
                    }
                    total_records += len(rows)
            
            sqlite_conn.close()
            
            # Сохраняем данные в основную базу
            await self._save_imported_data(session, user_id, imported_data)
            
            return {
                'success': True,
                'message': f'Успешно импортировано {total_records} записей',
                'tables_imported': list(imported_data.keys()),
                'total_records': total_records,
                'imported_data': imported_data
            }
            
        except Exception as e:
            logger.error(f"Ошибка импорта из DB файла: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Ошибка импорта из DB файла: {str(e)}'
            }
    
    async def _save_imported_data(
        self, 
        session, 
        user_id: int, 
        imported_data: Dict[str, Any]
    ):
        """Сохраняет импортированные данные в основную базу."""
        try:
            for table_name, table_data in imported_data.items():
                if table_name.lower() in ['health', 'health_metrics', 'fitness']:
                    await self._save_health_data(session, user_id, table_data)
                # Можно добавить другие типы данных по необходимости
                
        except Exception as e:
            logger.error(f"Ошибка сохранения импортированных данных: {e}", exc_info=True)
            raise
    
    async def _save_health_data(
        self, 
        session, 
        user_id: int, 
        table_data: Dict[str, Any]
    ):
        """Сохраняет данные здоровья в основную базу."""
        columns = table_data['columns']
        rows = table_data['rows']
        
        # Маппинг колонок
        column_mapping = {
            'steps': 'steps',
            'step_count': 'steps',
            'calories': 'calories',
            'calorie_count': 'calories',
            'sleep': 'sleep_minutes',
            'sleep_minutes': 'sleep_minutes',
            'sleep_time': 'sleep_minutes',
            'heart_rate': 'heart_rate_resting',
            'hr': 'heart_rate_resting',
            'weight': 'weight_kg',
            'weight_kg': 'weight_kg',
            'date': 'day',
            'day': 'day',
            'timestamp': 'day'
        }
        
        for row in rows:
            try:
                # Создаем словарь данных
                row_data = dict(zip(columns, row))
                
                # Определяем дату
                day = self._extract_date(row_data)
                if not day:
                    continue
                
                # Создаем или обновляем запись
                existing_record = (
                    await session.execute(
                        select(HealthMetric).where(
                            HealthMetric.user_id == user_id,
                            HealthMetric.day == day
                        )
                    )
                ).scalar_one_or_none()
                
                if existing_record:
                    # Обновляем существующую запись
                    self._update_health_metric(existing_record, row_data, column_mapping)
                else:
                    # Создаем новую запись
                    new_record = HealthMetric(
                        user_id=user_id,
                        day=day
                    )
                    self._update_health_metric(new_record, row_data, column_mapping)
                    session.add(new_record)
                
            except Exception as e:
                logger.warning(f"Ошибка обработки строки {row}: {e}")
                continue
        
        await session.commit()
    
    def _extract_date(self, row_data: Dict[str, Any]) -> Optional[date]:
        """Извлекает дату из данных строки."""
        date_fields = ['date', 'day', 'timestamp']
        
        for field in date_fields:
            if field in row_data:
                value = row_data[field]
                if value:
                    try:
                        if isinstance(value, str):
                            # Пробуем разные форматы даты
                            for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%Y/%m/%d']:
                                try:
                                    return datetime.strptime(value, fmt).date()
                                except ValueError:
                                    continue
                        elif isinstance(value, (int, float)):
                            # Unix timestamp
                            return datetime.fromtimestamp(value).date()
                    except Exception:
                        continue
        
        # Если не удалось извлечь дату, используем сегодняшнюю
        return date.today()
    
    def _update_health_metric(
        self, 
        metric: HealthMetric, 
        row_data: Dict[str, Any], 
        column_mapping: Dict[str, str]
    ):
        """Обновляет метрику здоровья данными из строки."""
        for source_col, target_field in column_mapping.items():
            if source_col in row_data and row_data[source_col] is not None:
                value = row_data[source_col]
                
                try:
                    if target_field == 'steps' and isinstance(value, (int, float)):
                        metric.steps = int(value)
                    elif target_field == 'calories' and isinstance(value, (int, float)):
                        metric.calories = int(value)
                    elif target_field == 'sleep_minutes' and isinstance(value, (int, float)):
                        metric.sleep_minutes = int(value)
                    elif target_field == 'heart_rate_resting' and isinstance(value, (int, float)):
                        metric.heart_rate_resting = int(value)
                    elif target_field == 'weight_kg' and isinstance(value, (int, float)):
                        metric.weight_kg = float(value)
                except (ValueError, TypeError):
                    logger.warning(f"Не удалось преобразовать значение {value} для поля {target_field}")
                    continue
    
    def get_supported_formats(self) -> List[str]:
        """Возвращает список поддерживаемых форматов файлов."""
        return self.supported_formats
    
    def get_db_extensions(self) -> List[str]:
        """Возвращает список поддерживаемых расширений баз данных."""
        return self.db_extensions
