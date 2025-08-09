## Gladiator Arena Life Bot

Асинхронный Telegram-бот (aiogram 3.x) для построения характера победителя: цели, привычки, финансы, продуктивность, рутины и питание. SQLAlchemy 2.0 async + PostgreSQL, напоминания (TG + email), интеграция с Google Calendar, экспорт в CSV/Excel и визуализация прогресса.

### Быстрый старт

1. Создайте .env на основе `.env.example`.
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Поднимите PostgreSQL и создайте БД (например, `arena_bot`).
4. Примените миграции (или быстрый init):
   - Рекомендуется Alembic: `alembic init migrations` → настройте `env.py` на `AsyncEngine` → `alembic revision --autogenerate -m "init"` → `alembic upgrade head`.
   - Для локального теста можно вызвать `create_all()` из `app/db/session.py` (не для продакшена).
5. Запуск бота (long polling):
   ```bash
   python -m app.bot
   ```

### Архитектура

Смотри `app/` модули: `handlers/`, `services/`, `db/models/`, `schemas/`, `utils/`.

### Экспорт/визуализация

Сервис `app/services/exporters.py` (CSV/Excel) и `app/services/visualization.py` (PNG графики) по пользователю и по сущностям.

### Google Calendar

Положите `credentials.json` в корень проекта или путь из `.env`. При первом запуске пройдите OAuth и сохраните `token.json`.

### Email

Заполните SMTP-настройки в `.env` (рекомендуется использовать app-password).

# voit_bot
Бот ментор
