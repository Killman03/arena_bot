#!/bin/bash

# Скрипт для создания резервной копии бота перед обновлением
# Использование: ./deployment_backup_script.sh

set -e

# Настройки
BACKUP_DIR="/home/backups/voit_bot_$(date +%Y%m%d_%H%M%S)"
BOT_DIR="/path/to/your/bot"  # Замените на реальный путь к боту
DB_NAME="arena_bot"  # Имя базы данных из alembic.ini

echo "Создание резервной копии бота..."

# Создаем директорию для резервной копии
mkdir -p "$BACKUP_DIR"

# 1. Резервная копия базы данных
echo "Создание резервной копии базы данных..."
pg_dump -h localhost -U postgres -d "$DB_NAME" > "$BACKUP_DIR/database_backup.sql"

# 2. Резервная копия файлов бота (исключая логи и кэш)
echo "Создание резервной копии файлов бота..."
rsync -av --exclude='__pycache__' --exclude='*.log' --exclude='.git' "$BOT_DIR/" "$BACKUP_DIR/bot_files/"

# 3. Резервная копия конфигурации
echo "Создание резервной копии конфигурации..."
cp "$BOT_DIR/.env" "$BACKUP_DIR/" 2>/dev/null || echo "Файл .env не найден"
cp "$BOT_DIR/alembic.ini" "$BACKUP_DIR/"

# 4. Информация о текущем состоянии
echo "Сбор информации о текущем состоянии..."
echo "Дата резервной копии: $(date)" > "$BACKUP_DIR/backup_info.txt"
echo "Версия Python: $(python3 --version)" >> "$BACKUP_DIR/backup_info.txt"
echo "Текущая директория бота: $BOT_DIR" >> "$BACKUP_DIR/backup_info.txt"

# Создаем архив
echo "Создание архива резервной копии..."
tar -czf "$BACKUP_DIR.tar.gz" -C "$(dirname "$BACKUP_DIR")" "$(basename "$BACKUP_DIR")"

# Удаляем временную директорию
rm -rf "$BACKUP_DIR"

echo "Резервная копия создана: $BACKUP_DIR.tar.gz"
echo "Размер архива: $(du -h "$BACKUP_DIR.tar.gz" | cut -f1)"
