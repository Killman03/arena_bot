#!/bin/bash

# Скрипт для безопасного обновления бота на VPS
# Использование: ./deployment_update_script.sh

set -e

# Настройки
BOT_DIR="/path/to/your/bot"  # Замените на реальный путь к боту
BACKUP_DIR="/home/backups"
SERVICE_NAME="voit_bot"  # Имя systemd сервиса

echo "Начинаем обновление бота..."

# 1. Проверяем, что мы в правильной директории
if [ ! -f "$BOT_DIR/main.py" ]; then
    echo "Ошибка: Файл main.py не найден в $BOT_DIR"
    exit 1
fi

# 2. Останавливаем бота
echo "Останавливаем бота..."
sudo systemctl stop "$SERVICE_NAME" || echo "Сервис не был запущен"

# 3. Создаем резервную копию текущей версии
echo "Создание резервной копии текущей версии..."
BACKUP_FILE="$BACKUP_DIR/voit_bot_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$BACKUP_FILE" -C "$(dirname "$BOT_DIR")" "$(basename "$BOT_DIR")" --exclude='__pycache__' --exclude='*.log'
echo "Резервная копия создана: $BACKUP_FILE"

# 4. Обновляем код бота
echo "Обновление кода бота..."
# Здесь нужно заменить на ваш способ обновления кода
# Например, через git:
# cd "$BOT_DIR"
# git fetch origin
# git reset --hard origin/main

# Или через rsync с локальной машины:
# rsync -av --delete /local/path/to/bot/ "$BOT_DIR/"

# 5. Обновляем зависимости
echo "Обновление зависимостей Python..."
cd "$BOT_DIR"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# 6. Применяем миграции базы данных
echo "Применение миграций базы данных..."
alembic upgrade head

# 7. Проверяем конфигурацию
echo "Проверка конфигурации..."
if [ ! -f ".env" ]; then
    echo "Внимание: Файл .env не найден. Убедитесь, что он существует."
fi

# 8. Проверяем синтаксис Python
echo "Проверка синтаксиса Python..."
python3 -m py_compile main.py
find . -name "*.py" -exec python3 -m py_compile {} \;

# 9. Запускаем бота
echo "Запуск бота..."
sudo systemctl start "$SERVICE_NAME"

# 10. Проверяем статус
echo "Проверка статуса сервиса..."
sleep 5
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Бот успешно запущен!"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l
else
    echo "❌ Ошибка запуска бота!"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l
    echo "Проверьте логи: sudo journalctl -u $SERVICE_NAME -f"
    exit 1
fi

echo "Обновление завершено успешно!"
