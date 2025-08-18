from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, HealthMetric


class GoogleDriveService:
    """Сервис для интеграции с Google Drive API для чтения данных здоровья."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.metadata.readonly'
    ]
    
    def __init__(self):
        self.service = None
    
    def get_authorization_url(self, user_id: int) -> str:
        """Генерирует URL для авторизации пользователя."""
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uris": [settings.google_redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            self.SCOPES
        )
        flow.redirect_uri = settings.google_redirect_uri
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=str(user_id)
        )
        return authorization_url
    
    def exchange_code_for_tokens(self, code: str) -> dict:
        """Обменивает код авторизации на токены."""
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uris": [settings.google_redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            self.SCOPES
        )
        flow.redirect_uri = settings.google_redirect_uri
        flow.fetch_token(code=code)
        return {
            'token': flow.credentials.token,
            'refresh_token': flow.credentials.refresh_token,
            'token_uri': flow.credentials.token_uri,
            'client_id': flow.credentials.client_id,
            'client_secret': flow.credentials.client_secret,
            'scopes': flow.credentials.scopes
        }
    
    def _get_service(self, credentials_dict: dict):
        """Создает сервис Google Drive API."""
        credentials = Credentials.from_authorized_user_info(credentials_dict)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        return build('drive', 'v3', credentials=credentials)
    
    async def find_health_files(self, session: AsyncSession, user_id: int, credentials_dict: dict) -> List[Dict[str, Any]]:
        """Находит файлы с данными здоровья на Google Drive."""
        try:
            service = self._get_service(credentials_dict)
            
            # Ищем файлы с данными здоровья (CSV, Excel, JSON)
            # Health Sync обычно создает файлы с определенными именами
            query = "("
            query += "name contains 'health' or "
            query += "name contains 'fitness' or "
            query += "name contains 'steps' or "
            query += "name contains 'sleep' or "
            query += "name contains 'activity' or "
            query += "name contains 'HealthSync' or "
            query += "name contains 'GoogleFit'"
            query += ") and ("
            query += "mimeType = 'text/csv' or "
            query += "mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or "
            query += "mimeType = 'application/json'"
            query += ")"
            
            results = service.files().list(
                q=query,
                pageSize=50,
                fields="files(id,name,mimeType,modifiedTime,size)"
            ).execute()
            
            files = results.get('files', [])
            
            # Сортируем по дате изменения (новые сначала)
            files.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
            
            return files
            
        except Exception as e:
            return []
    
    async def read_health_file(self, session: AsyncSession, user_id: int, credentials_dict: dict, file_id: str, file_name: str) -> Dict[str, Any]:
        """Читает файл с данными здоровья и парсит его."""
        try:
            service = self._get_service(credentials_dict)
            
            # Скачиваем файл
            request = service.files().get_media(fileId=file_id)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            file.seek(0)
            content = file.read().decode('utf-8')
            
            # Парсим в зависимости от типа файла
            if file_name.lower().endswith('.csv'):
                return await self._parse_csv_health_data(content)
            elif file_name.lower().endswith('.json'):
                return await self._parse_json_health_data(content)
            elif file_name.lower().endswith(('.xlsx', '.xls')):
                return await self._parse_excel_health_data(content)
            else:
                return {'error': f'Неподдерживаемый формат файла: {file_name}'}
                
        except Exception as e:
            return {'error': f'Ошибка чтения файла: {str(e)}'}
    
    async def _parse_csv_health_data(self, content: str) -> Dict[str, Any]:
        """Парсит CSV файл с данными здоровья."""
        try:
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
            
            if not rows:
                return {'error': 'Файл пустой или не содержит данных'}
            
            # Анализируем структуру данных
            headers = list(rows[0].keys())
            
            # Ищем колонки с данными здоровья
            health_data = {
                'steps': [],
                'calories': [],
                'sleep': [],
                'heart_rate': [],
                'weight': [],
                'blood_pressure': []
            }
            
            # Маппинг возможных названий колонок
            column_mapping = {
                'steps': ['steps', 'step_count', 'шаги', 'количество шагов'],
                'calories': ['calories', 'calories_burned', 'калории', 'сожжено калорий'],
                'sleep': ['sleep', 'sleep_duration', 'sleep_minutes', 'сон', 'длительность сна'],
                'heart_rate': ['heart_rate', 'hr', 'bpm', 'пульс', 'частота пульса'],
                'weight': ['weight', 'weight_kg', 'вес', 'масса'],
                'blood_pressure': ['blood_pressure', 'bp', 'давление', 'артериальное давление']
            }
            
            # Находим соответствующие колонки
            found_columns = {}
            for metric, possible_names in column_mapping.items():
                for header in headers:
                    if any(name.lower() in header.lower() for name in possible_names):
                        found_columns[metric] = header
                        break
            
            # Парсим данные
            for row in rows:
                for metric, column in found_columns.items():
                    try:
                        value = row.get(column, '').strip()
                        if value and value != '':
                            if metric in ['steps', 'calories', 'sleep', 'heart_rate']:
                                health_data[metric].append(int(float(value)))
                            elif metric == 'weight':
                                health_data[metric].append(float(value))
                            elif metric == 'blood_pressure':
                                health_data[metric].append(value)
                    except (ValueError, TypeError):
                        continue
            
            return {
                'success': True,
                'data': health_data,
                'found_columns': found_columns,
                'total_rows': len(rows)
            }
            
        except Exception as e:
            return {'error': f'Ошибка парсинга CSV: {str(e)}'}
    
    async def _parse_json_health_data(self, content: str) -> Dict[str, Any]:
        """Парсит JSON файл с данными здоровья."""
        try:
            data = json.loads(content)
            
            # Адаптируем под возможные структуры JSON от Health Sync
            health_data = {
                'steps': [],
                'calories': [],
                'sleep': [],
                'heart_rate': [],
                'weight': [],
                'blood_pressure': []
            }
            
            # Рекурсивно ищем данные здоровья в JSON
            def extract_health_data(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        
                        # Ищем ключи, связанные со здоровьем
                        key_lower = key.lower()
                        if any(term in key_lower for term in ['step', 'шаг']):
                            if isinstance(value, (int, float)):
                                health_data['steps'].append(int(value))
                        elif any(term in key_lower for term in ['calori', 'калори']):
                            if isinstance(value, (int, float)):
                                health_data['calories'].append(int(value))
                        elif any(term in key_lower for term in ['sleep', 'сон']):
                            if isinstance(value, (int, float)):
                                health_data['sleep'].append(int(value))
                        elif any(term in key_lower for term in ['heart', 'pulse', 'пульс']):
                            if isinstance(value, (int, float)):
                                health_data['heart_rate'].append(int(value))
                        elif any(term in key_lower for term in ['weight', 'вес']):
                            if isinstance(value, (int, float)):
                                health_data['weight'].append(float(value))
                        elif any(term in key_lower for term in ['pressure', 'давление']):
                            if isinstance(value, (str, int, float)):
                                health_data['blood_pressure'].append(str(value))
                        
                        extract_health_data(value, current_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        extract_health_data(item, f"{path}[{i}]")
            
            extract_health_data(data)
            
            return {
                'success': True,
                'data': health_data,
                'total_entries': len(data) if isinstance(data, list) else 1
            }
            
        except Exception as e:
            return {'error': f'Ошибка парсинга JSON: {str(e)}'}
    
    async def _parse_excel_health_data(self, content: bytes) -> Dict[str, Any]:
        """Парсит Excel файл с данными здоровья."""
        try:
            import pandas as pd
            
            # Читаем Excel файл
            df = pd.read_excel(io.BytesIO(content))
            
            health_data = {
                'steps': [],
                'calories': [],
                'sleep': [],
                'heart_rate': [],
                'weight': [],
                'blood_pressure': []
            }
            
            # Анализируем колонки
            columns = df.columns.tolist()
            
            # Маппинг колонок (аналогично CSV)
            column_mapping = {
                'steps': ['steps', 'step_count', 'шаги', 'количество шагов'],
                'calories': ['calories', 'calories_burned', 'калории', 'сожжено калорий'],
                'sleep': ['sleep', 'sleep_duration', 'sleep_minutes', 'сон', 'длительность сна'],
                'heart_rate': ['heart_rate', 'hr', 'bpm', 'пульс', 'частота пульса'],
                'weight': ['weight', 'weight_kg', 'вес', 'масса'],
                'blood_pressure': ['blood_pressure', 'bp', 'давление', 'артериальное давление']
            }
            
            found_columns = {}
            for metric, possible_names in column_mapping.items():
                for col in columns:
                    if any(name.lower() in str(col).lower() for name in possible_names):
                        found_columns[metric] = col
                        break
            
            # Извлекаем данные
            for metric, column in found_columns.items():
                try:
                    values = df[column].dropna().tolist()
                    for value in values:
                        if metric in ['steps', 'calories', 'sleep', 'heart_rate']:
                            health_data[metric].append(int(float(value)))
                        elif metric == 'weight':
                            health_data[metric].append(float(value))
                        elif metric == 'blood_pressure':
                            health_data[metric].append(str(value))
                except (ValueError, TypeError):
                    continue
            
            return {
                'success': True,
                'data': health_data,
                'found_columns': found_columns,
                'total_rows': len(df)
            }
            
        except Exception as e:
            return {'error': f'Ошибка парсинга Excel: {str(e)}'}
    
    async def sync_health_data_from_drive(self, session: AsyncSession, user_id: int, credentials_dict: dict, days_back: int = 7) -> Dict[str, Any]:
        """Синхронизирует данные здоровья из Google Drive."""
        try:
            # Находим файлы с данными здоровья
            files = await self.find_health_files(session, user_id, credentials_dict)
            
            if not files:
                return {'error': 'Не найдено файлов с данными здоровья на Google Drive'}
            
            # Берем самый новый файл
            latest_file = files[0]
            
            # Читаем и парсим файл
            parsed_data = await self.read_health_file(
                session, user_id, credentials_dict, 
                latest_file['id'], latest_file['name']
            )
            
            if 'error' in parsed_data:
                return parsed_data
            
            # Сохраняем данные в базу
            if parsed_data.get('success'):
                await self._save_parsed_health_data(session, user_id, parsed_data['data'])
            
            return {
                'success': True,
                'file_processed': latest_file['name'],
                'data_summary': {
                    'steps_entries': len(parsed_data['data']['steps']),
                    'calories_entries': len(parsed_data['data']['calories']),
                    'sleep_entries': len(parsed_data['data']['sleep']),
                    'heart_rate_entries': len(parsed_data['data']['heart_rate']),
                    'weight_entries': len(parsed_data['data']['weight']),
                    'blood_pressure_entries': len(parsed_data['data']['blood_pressure'])
                }
            }
            
        except Exception as e:
            return {'error': f'Ошибка синхронизации: {str(e)}'}
    
    async def _save_parsed_health_data(self, session: AsyncSession, user_id: int, data: Dict[str, List]):
        """Сохраняет распарсенные данные здоровья в базу данных."""
        today = datetime.now().date()
        
        # Создаем запись за сегодня
        health_metric = HealthMetric(
            user_id=user_id,
            day=today,
            steps=data['steps'][-1] if data['steps'] else None,
            calories=data['calories'][-1] if data['calories'] else None,
            sleep_minutes=data['sleep'][-1] if data['sleep'] else None,
            heart_rate_resting=data['heart_rate'][-1] if data['heart_rate'] else None,
            weight_kg=data['weight'][-1] if data['weight'] else None,
            source='google_drive'
        )
        
        # Проверяем, есть ли уже запись за сегодня
        existing_record = (
            await session.execute(
                select(HealthMetric).where(
                    HealthMetric.user_id == user_id,
                    HealthMetric.day == today
                )
            )
        ).scalar_one_or_none()
        
        if existing_record:
            # Обновляем существующую запись
            if data['steps']:
                existing_record.steps = data['steps'][-1]
            if data['calories']:
                existing_record.calories = data['calories'][-1]
            if data['sleep']:
                existing_record.sleep_minutes = data['sleep'][-1]
            if data['heart_rate']:
                existing_record.heart_rate_resting = data['heart_rate'][-1]
            if data['weight']:
                existing_record.weight_kg = data['weight'][-1]
            existing_record.source = 'google_drive'
        else:
            # Создаем новую запись
            session.add(health_metric)
        
        await session.commit()
