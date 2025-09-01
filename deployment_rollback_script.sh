#!/bin/bash

# Скрипт для отката изменений в случае проблем
# Использование: ./deployment_rollback_script.sh BACKUP_FILE

set -e

if [ $# -eq 0 ]; then
    echo "Использование: $0 BACKUP_FILE"
    echo "Пример: $0 /home/backups/voit_bot_backup_20250127_143022.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"
BOT_DIR="/path/to/your/bot"  # Замените на реальный путь к боту
SERVICE_NAME="voit_bot"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Ошибка: Файл резервной копии не найден: $BACKUP_FILE"
    exit 1
fi

echo "Начинаем откат изменений..."

# 1. Останавливаем бота
echo "Останавливаем бота..."
sudo systemctl stop "$SERVICE_NAME" || echo "Сервис не был запущен"

# 2. Создаем резервную копию текущего состояния (на всякий случай)
echo "Создание резервной копии текущего состояния..."
CURRENT_BACKUP="/home/backups/current_state_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$CURRENT_BACKUP" -C "$(dirname "$BOT_DIR")" "$(basename "$BOT_DIR")" --exclude='__pycache__' --exclude='*.log'

# 3. Удаляем текущую версию
echo "Удаление текущей версии..."
rm -rf "$BOT_DIR"

# 4. Восстанавливаем из резервной копии
echo "Восстановление из резервной копии..."
tar -xzf "$BACKUP_FILE" -C "$(dirname "$BOT_DIR")"

# 5. Проверяем, что файлы восстановлены
if [ ! -f "$BOT_DIR/main.py" ]; then
    echo "Ошибка: Восстановление не удалось"
    exit 1
fi

# 6. Восстанавливаем зависимости
echo "Восстановление зависимостей..."
cd "$BOT_DIR"
python3 -m pip install -r requirements.txt

# 7. Откатываем миграции базы данных (если нужно)
echo "Проверка миграций базы данных..."
# Внимание: Откат миграций может привести к потере данных!
# Раскомментируйте только если уверены:
# alembic downgrade -1

# 8. Запускаем бота
echo "Запуск бота..."
sudo systemctl start "$SERVICE_NAME"

# 9. Проверяем статус
echo "Проверка статуса сервиса..."
sleep 5
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Откат выполнен успешно! Бот запущен."
    sudo systemctl status "$SERVICE_NAME" --no-pager -l
else
    echo "❌ Ошибка запуска бота после отката!"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l
    echo "Проверьте логи: sudo journalctl -u $SERVICE_NAME -f"
    exit 1
fi

echo "Откат завершен успешно!"
echo "Текущее состояние сохранено в: $CURRENT_BACKUP"
