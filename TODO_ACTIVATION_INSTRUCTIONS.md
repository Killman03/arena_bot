# 📝 Инструкция по активации To-Do раздела

## 🚀 Шаг 1: Создание таблицы в базе данных

Чтобы активировать To-Do раздел, нужно создать таблицу `todos` в вашей базе данных PostgreSQL.

### Вариант 1: Через pgAdmin или другой GUI-клиент
1. Откройте ваш клиент PostgreSQL (pgAdmin, DBeaver, etc.)
2. Подключитесь к базе данных `voit_bot`
3. Выполните SQL-скрипт из файла `create_todos_table.sql`

### Вариант 2: Через командную строку
```bash
psql -h localhost -U postgres -d voit_bot -f create_todos_table.sql
```

### Вариант 3: Через Python (если есть доступ к базе)
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="voit_bot",
    user="postgres",
    password="your_password"
)

with conn.cursor() as cur:
    with open('create_todos_table.sql', 'r') as f:
        cur.execute(f.read())
    conn.commit()

conn.close()
```

## 🔧 Шаг 2: Активация в коде

После создания таблицы, раскомментируйте следующие строки:

### В файле `app/db/models/__init__.py`:
```python
from .todo import Todo  # Уберите комментарий
```

### В файле `app/db/models/__init__.py` (в __all__):
```python
"Todo",  # Уберите комментарий
```

### В файле `app/handlers/__init__.py`:
```python
from .todo import router as todo_router  # Уберите комментарий
```

### В файле `app/handlers/__init__.py` (в setup_routers):
```python
router.include_router(todo_router)  # Уберите комментарий
```

## ✅ Шаг 3: Перезапуск бота

После всех изменений перезапустите бота:
```bash
python -m app.bot
```

## 🎯 Что получится после активации

- **Кнопка "📝 To-Do"** в главном меню
- **Полноценный To-Do раздел** с возможностью:
  - Добавления задач
  - Редактирования задач
  - Удаления задач
  - Отметки выполнения
  - Управления ежедневными делами
  - Установки приоритетов
- **Вечерние напоминания** в 20:00 о составлении списка на завтра
- **Умные функции**: автопарсинг дат, копирование задач, приоритизация

## 🆘 Если что-то не работает

1. Проверьте, что таблица `todos` создана в базе данных
2. Убедитесь, что все импорты раскомментированы
3. Проверьте логи бота на наличие ошибок
4. Убедитесь, что база данных доступна и работает

## 📋 Структура таблицы todos

```sql
CREATE TABLE todos (
    id SERIAL PRIMARY KEY,                    -- Уникальный ID
    user_id INTEGER NOT NULL,                 -- Ссылка на пользователя
    title VARCHAR(500) NOT NULL,              -- Название задачи
    description TEXT,                         -- Описание задачи
    due_date DATE NOT NULL,                   -- Дата выполнения
    is_completed BOOLEAN DEFAULT FALSE,       -- Статус выполнения
    is_daily BOOLEAN DEFAULT FALSE,           -- Ежедневная задача
    priority VARCHAR(20) DEFAULT 'medium',    -- Приоритет
    created_at TIMESTAMP DEFAULT NOW()        -- Время создания
);
```

После выполнения всех шагов To-Do раздел будет полностью функционален! 🎉
