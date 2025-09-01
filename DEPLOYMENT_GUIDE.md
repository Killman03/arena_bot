# Руководство по безопасному обновлению Voit Bot на VPS

## Обзор

Это руководство поможет вам безопасно обновить бота на VPS, сохранив все данные пользователей.

## Что сохраняется при обновлении

✅ **Сохраняется:**
- Все данные пользователей в PostgreSQL
- Настройки пользователей (timezone, preferences)
- Финансовые данные
- Цели и задачи
- Данные о здоровье и питании
- История взаимодействий
- Напоминания и расписания

❌ **Не сохраняется (если не настроено):**
- Логи бота
- Временные файлы
- Кэш Python

## Подготовка к обновлению

### 1. Настройка скриптов

Отредактируйте следующие файлы, указав правильные пути:

```bash
# В deployment_backup_script.sh
BOT_DIR="/home/your_username/voit_bot"  # Путь к вашему боту
DB_NAME="arena_bot"  # Имя вашей базы данных

# В deployment_update_script.sh
BOT_DIR="/home/your_username/voit_bot"
SERVICE_NAME="voit_bot"

# В deployment_rollback_script.sh
BOT_DIR="/home/your_username/voit_bot"
SERVICE_NAME="voit_bot"
```

### 2. Настройка systemd сервиса

Отредактируйте `voit_bot.service`:

```bash
# Замените на ваши значения
User=your_username
Group=your_username
WorkingDirectory=/home/your_username/voit_bot
Environment=PATH=/home/your_username/voit_bot/venv/bin
ExecStart=/home/your_username/voit_bot/venv/bin/python main.py
ReadWritePaths=/home/your_username/voit_bot
```

Установите сервис:

```bash
sudo cp voit_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable voit_bot
```

### 3. Создание директории для резервных копий

```bash
sudo mkdir -p /home/backups
sudo chown your_username:your_username /home/backups
```

## Процесс обновления

### Шаг 1: Создание резервной копии

```bash
chmod +x deployment_backup_script.sh
./deployment_backup_script.sh
```

### Шаг 2: Обновление кода

Выберите один из способов:

#### Вариант A: Через Git (рекомендуется)

```bash
cd /path/to/your/bot
git fetch origin
git reset --hard origin/main
```

#### Вариант B: Через rsync с локальной машины

```bash
rsync -av --delete /local/path/to/bot/ user@your-vps:/path/to/bot/
```

#### Вариант C: Через SCP

```bash
scp -r /local/path/to/bot/* user@your-vps:/path/to/bot/
```

### Шаг 3: Запуск скрипта обновления

```bash
chmod +x deployment_update_script.sh
./deployment_update_script.sh
```

## Проверка после обновления

### 1. Проверка статуса сервиса

```bash
sudo systemctl status voit_bot
```

### 2. Проверка логов

```bash
sudo journalctl -u voit_bot -f
```

### 3. Проверка базы данных

```bash
# Подключение к БД
psql -h localhost -U postgres -d arena_bot

# Проверка таблиц
\dt

# Проверка количества пользователей
SELECT COUNT(*) FROM users;

# Проверка последних записей
SELECT * FROM users ORDER BY created_at DESC LIMIT 5;
```

### 4. Тестирование бота

Отправьте боту команду `/start` и проверьте, что он отвечает корректно.

## Откат изменений (если что-то пошло не так)

### 1. Остановка бота

```bash
sudo systemctl stop voit_bot
```

### 2. Запуск скрипта отката

```bash
chmod +x deployment_rollback_script.sh
./deployment_rollback_script.sh /path/to/backup/file.tar.gz
```

## Мониторинг после обновления

### 1. Проверка использования ресурсов

```bash
# Использование памяти
ps aux | grep python

# Использование диска
df -h

# Логи в реальном времени
sudo journalctl -u voit_bot -f
```

### 2. Проверка подключений к БД

```bash
# Активные подключения
psql -h localhost -U postgres -d arena_bot -c "SELECT * FROM pg_stat_activity;"
```

## Частые проблемы и решения

### Проблема: Бот не запускается

**Решение:**
```bash
# Проверка логов
sudo journalctl -u voit_bot -n 50

# Проверка синтаксиса
python3 -m py_compile main.py

# Проверка зависимостей
pip list | grep -E "(aiogram|sqlalchemy|alembic)"
```

### Проблема: Ошибки миграции

**Решение:**
```bash
# Проверка текущей версии
alembic current

# Проверка истории миграций
alembic history

# Принудительное обновление
alembic upgrade head
```

### Проблема: Потеря данных

**Решение:**
```bash
# Восстановление из резервной копии БД
psql -h localhost -U postgres -d arena_bot < /path/to/backup/database_backup.sql
```

## Автоматизация

### Настройка автоматических резервных копий

Добавьте в crontab:

```bash
# Ежедневная резервная копия в 2:00
0 2 * * * /path/to/deployment_backup_script.sh

# Еженедельная полная резервная копия
0 3 * * 0 /path/to/deployment_backup_script.sh
```

### Мониторинг через systemd

```bash
# Автоматический перезапуск при сбое
sudo systemctl edit voit_bot

# Добавьте:
[Service]
Restart=always
RestartSec=10
```

## Контакты для поддержки

Если у вас возникли проблемы:

1. Проверьте логи: `sudo journalctl -u voit_bot -f`
2. Проверьте статус сервиса: `sudo systemctl status voit_bot`
3. Проверьте подключение к БД: `psql -h localhost -U postgres -d arena_bot`

## Безопасность

- Всегда создавайте резервные копии перед обновлением
- Тестируйте обновления на тестовой среде
- Используйте виртуальные окружения Python
- Регулярно обновляйте зависимости
- Мониторьте использование ресурсов
