from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, HealthMetric


class GoogleFitService:
    """Сервис для интеграции с Google Fit API."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/fitness.activity.read',
        'https://www.googleapis.com/auth/fitness.body.read',
        'https://www.googleapis.com/auth/fitness.heart_rate.read',
        'https://www.googleapis.com/auth/fitness.sleep.read'
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
        """Создает сервис Google Fit API."""
        credentials = Credentials.from_authorized_user_info(credentials_dict)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        return build('fitness', 'v1', credentials=credentials)
    
    async def sync_health_data(self, session: AsyncSession, user_id: int, credentials_dict: dict, days_back: int = 7) -> dict:
        """Синхронизирует данные здоровья из Google Fit."""
        try:
            service = self._get_service(credentials_dict)
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)
            
            # Конвертируем в наносекунды (Google Fit использует наносекунды)
            start_ns = int(start_time.timestamp() * 1000000000)
            end_ns = int(end_time.timestamp() * 1000000000)
            
            results = {
                'steps': 0,
                'calories': 0,
                'sleep_minutes': 0,
                'heart_rate': None,
                'weight': None
            }
            
            # Получаем шаги
            steps_data = service.users().dataSources().datasets().get(
                userId='me',
                dataSourceId='derived:com.google.step_count.delta:com.google.android.gms:estimated_steps',
                datasetId=f'{start_ns}-{end_ns}'
            ).execute()
            
            if 'point' in steps_data:
                for point in steps_data['point']:
                    if 'value' in point and len(point['value']) > 0:
                        results['steps'] += int(point['value'][0].get('intVal', 0))
            
            # Получаем калории
            calories_data = service.users().dataSources().datasets().get(
                userId='me',
                dataSourceId='derived:com.google.calories.expended:com.google.android.gms:from_activities',
                datasetId=f'{start_ns}-{end_ns}'
            ).execute()
            
            if 'point' in calories_data:
                for point in calories_data['point']:
                    if 'value' in point and len(point['value']) > 0:
                        results['calories'] += int(point['value'][0].get('fpVal', 0))
            
            # Получаем сон
            sleep_data = service.users().dataSources().datasets().get(
                userId='me',
                dataSourceId='derived:com.google.sleep.segment:com.google.android.gms:sleep_from_activity',
                datasetId=f'{start_ns}-{end_ns}'
            ).execute()
            
            if 'point' in sleep_data:
                for point in sleep_data['point']:
                    if 'value' in point and len(point['value']) > 0:
                        sleep_duration = int(point['value'][0].get('intVal', 0))
                        results['sleep_minutes'] += sleep_duration // 60000000000  # конвертируем наносекунды в минуты
            
            # Получаем пульс покоя (последнее значение)
            hr_data = service.users().dataSources().datasets().get(
                userId='me',
                dataSourceId='derived:com.google.heart_rate.bpm:com.google.android.gms:resting_heart_rate',
                datasetId=f'{start_ns}-{end_ns}'
            ).execute()
            
            if 'point' in hr_data and len(hr_data['point']) > 0:
                last_point = hr_data['point'][-1]
                if 'value' in last_point and len(last_point['value']) > 0:
                    results['heart_rate'] = int(last_point['value'][0].get('fpVal', 0))
            
            # Получаем вес (последнее значение)
            weight_data = service.users().dataSources().datasets().get(
                userId='me',
                dataSourceId='derived:com.google.weight:com.google.android.gms:merge_weight',
                datasetId=f'{start_ns}-{end_ns}'
            ).execute()
            
            if 'point' in weight_data and len(weight_data['point']) > 0:
                last_point = weight_data['point'][-1]
                if 'value' in last_point and len(last_point['value']) > 0:
                    results['weight'] = float(last_point['value'][0].get('fpVal', 0))
            
            # Сохраняем данные в базу
            await self._save_health_data(session, user_id, results, end_time.date())
            
            return results
            
        except Exception as e:
            return {'error': str(e)}
    
    async def _save_health_data(self, session: AsyncSession, user_id: int, data: dict, date: datetime.date):
        """Сохраняет данные здоровья в базу данных."""
        # Проверяем, есть ли уже запись за этот день
        existing_record = (
            await session.execute(
                select(HealthMetric).where(
                    HealthMetric.user_id == user_id,
                    HealthMetric.day == date
                )
            )
        ).scalar_one_or_none()
        
        if existing_record:
            # Обновляем существующую запись
            if data.get('steps'):
                existing_record.steps = data['steps']
            if data.get('calories'):
                existing_record.calories = data['calories']
            if data.get('sleep_minutes'):
                existing_record.sleep_minutes = data['sleep_minutes']
            if data.get('heart_rate'):
                existing_record.heart_rate_resting = data['heart_rate']
            if data.get('weight'):
                existing_record.weight_kg = data['weight']
            existing_record.source = 'google_fit'
        else:
            # Создаем новую запись
            new_record = HealthMetric(
                user_id=user_id,
                day=date,
                steps=data.get('steps'),
                calories=data.get('calories'),
                sleep_minutes=data.get('sleep_minutes'),
                heart_rate_resting=data.get('heart_rate'),
                weight_kg=data.get('weight'),
                source='google_fit'
            )
            session.add(new_record)
        
        await session.commit()
