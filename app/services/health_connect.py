"""
Health Connect API integration service.

Health Connect is Google's new health data platform for Android 14+.
It provides a unified API for accessing health data from various apps.
"""

import asyncio
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, HealthMetric, GoogleFitToken
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class HealthConnectData:
    """Data structure for Health Connect metrics."""
    steps: Optional[int] = None
    calories: Optional[int] = None
    sleep_minutes: Optional[int] = None
    heart_rate: Optional[int] = None
    weight_kg: Optional[float] = None
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    distance_meters: Optional[float] = None
    active_minutes: Optional[int] = None
    hydration_ml: Optional[int] = None
    source: str = "health_connect"


class HealthConnectService:
    """Service for integrating with Health Connect API."""
    
    def __init__(self):
        self.base_url = "https://www.googleapis.com/fitness/v1"
        self.health_connect_url = "https://healthconnect.googleapis.com/v1"
        self.scopes = [
            "https://www.googleapis.com/auth/fitness.activity.read",
            "https://www.googleapis.com/auth/fitness.body.read",
            "https://www.googleapis.com/auth/fitness.heart_rate.read",
            "https://www.googleapis.com/auth/fitness.location.read",
            "https://www.googleapis.com/auth/fitness.nutrition.read",
            "https://www.googleapis.com/auth/fitness.sleep.read"
        ]
    
    def get_authorization_url(self, user_id: int) -> str:
        """Generate OAuth authorization URL for Health Connect."""
        from app.services.google_fit import GoogleFitService
        
        # Используем Google Fit OAuth для Health Connect
        google_service = GoogleFitService()
        return google_service.get_authorization_url(user_id)
    
    async def exchange_code_for_tokens(self, auth_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens."""
        from app.services.google_fit import GoogleFitService
        
        # Используем Google Fit OAuth flow
        google_service = GoogleFitService()
        return google_service.exchange_code_for_tokens(auth_code)
    
    async def get_health_data(
        self, 
        session: AsyncSession, 
        user_id: int, 
        credentials: Dict[str, Any],
        days_back: int = 7
    ) -> Dict[str, Any]:
        """
        Fetch health data from Health Connect via Google Fit API.
        
        Args:
            session: Database session
            user_id: User ID
            credentials: OAuth credentials
            days_back: Number of days to fetch data for
            
        Returns:
            Dictionary with health data and metadata
        """
        try:
            # Получаем данные через Google Fit API (Health Connect пока не имеет прямого API)
            # В будущем можно будет заменить на прямой Health Connect API
            
            from app.services.google_fit import GoogleFitService
            google_service = GoogleFitService()
            
            # Получаем данные через Google Fit
            result = await google_service.sync_health_data(
                session, user_id, credentials, days_back
            )
            
            if 'error' in result:
                return {'error': result['error']}
            
            # Конвертируем в формат Health Connect
            health_data = HealthConnectData(
                steps=result.get('steps'),
                calories=result.get('calories'),
                sleep_minutes=result.get('sleep_minutes'),
                heart_rate=result.get('heart_rate'),
                weight_kg=result.get('weight'),
                source="health_connect"
            )
            
            return {
                'success': True,
                'data': health_data,
                'source': 'health_connect_via_google_fit',
                'days_processed': days_back
            }
            
        except Exception as e:
            logger.error(f"Error fetching Health Connect data: {e}")
            return {'error': str(e)}
    
    async def sync_health_data(
        self, 
        session: AsyncSession, 
        user_id: int, 
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sync health data from Health Connect and save to database.
        
        Args:
            session: Database session
            user_id: User ID
            credentials: OAuth credentials
            
        Returns:
            Dictionary with sync results
        """
        try:
            # Получаем данные за последние 7 дней
            result = await self.get_health_data(session, user_id, credentials, days_back=7)
            
            if 'error' in result:
                return {'error': result['error']}
            
            health_data = result['data']
            
            # Сохраняем данные в базу
            saved_metrics = []
            today = date.today()
            
            # Создаем или обновляем запись за сегодня
            existing_metric = (
                await session.execute(
                    select(HealthMetric).where(
                        HealthMetric.user_id == user_id,
                        HealthMetric.day == today
                    )
                )
            ).scalar_one_or_none()
            
            if not existing_metric:
                existing_metric = HealthMetric(
                    user_id=user_id,
                    day=today,
                    source="health_connect"
                )
                session.add(existing_metric)
            
            # Обновляем метрики
            if health_data.steps is not None:
                existing_metric.steps = health_data.steps
            if health_data.calories is not None:
                existing_metric.calories = health_data.calories
            if health_data.sleep_minutes is not None:
                existing_metric.sleep_minutes = health_data.sleep_minutes
            if health_data.heart_rate is not None:
                existing_metric.heart_rate_resting = health_data.heart_rate
            if health_data.weight_kg is not None:
                existing_metric.weight_kg = health_data.weight_kg
            if health_data.systolic is not None:
                existing_metric.systolic = health_data.systolic
            if health_data.diastolic is not None:
                existing_metric.diastolic = health_data.diastolic
            
            await session.commit()
            saved_metrics.append(today)
            
            return {
                'success': True,
                'metrics_saved': len(saved_metrics),
                'data_summary': {
                    'steps': health_data.steps,
                    'calories': health_data.calories,
                    'sleep_minutes': health_data.sleep_minutes,
                    'heart_rate': health_data.heart_rate,
                    'weight_kg': health_data.weight_kg,
                    'systolic': health_data.systolic,
                    'diastolic': health_data.diastolic
                },
                'source': 'health_connect'
            }
            
        except Exception as e:
            logger.error(f"Error syncing Health Connect data: {e}")
            return {'error': str(e)}
    
    async def get_supported_data_types(self) -> List[str]:
        """Get list of supported health data types."""
        return [
            "steps",
            "calories",
            "sleep",
            "heart_rate", 
            "weight",
            "blood_pressure",
            "distance",
            "active_minutes",
            "hydration"
        ]
    
    async def check_health_connect_availability(self, user_id: int) -> Dict[str, Any]:
        """
        Check if Health Connect is available for the user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with availability status
        """
        try:
            # Проверяем, есть ли подключенная интеграция
            async with session_scope() as session:
                google_token = (
                    await session.execute(
                        select(GoogleFitToken).where(
                            GoogleFitToken.user_id == user_id,
                            GoogleFitToken.integration_type == "google_fit"
                        )
                    )
                ).scalar_one_or_none()
                
                if google_token:
                    return {
                        'available': True,
                        'status': 'connected',
                        'message': 'Health Connect доступен через Google Fit'
                    }
                else:
                    return {
                        'available': False,
                        'status': 'not_connected',
                        'message': 'Подключите Google Fit для доступа к Health Connect'
                    }
                    
        except Exception as e:
            logger.error(f"Error checking Health Connect availability: {e}")
            return {
                'available': False,
                'status': 'error',
                'message': f'Ошибка проверки: {str(e)}'
            }


# Импорт для избежания циклических зависимостей
from app.db.session import session_scope
