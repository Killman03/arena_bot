# Чек-лист настройки Google Cloud Console

## ✅ Шаг 1: Создание проекта
- [ ] Открыть [Google Cloud Console](https://console.cloud.google.com/)
- [ ] Создать новый проект "Voit Bot Integration"
- [ ] Выбрать проект как активный

## ✅ Шаг 2: Включение API
- [ ] Включить Google Drive API
- [ ] Включить Google Fit API
- [ ] Дождаться активации API

## ✅ Шаг 3: Настройка OAuth
- [ ] Перейти в "Экраны согласия OAuth"
- [ ] Выбрать тип: Внешний
- [ ] Заполнить название: "Voit Bot"
- [ ] Добавить email пользователя
- [ ] Добавить email поддержки

## ✅ Шаг 4: Области доступа
- [ ] Добавить область: `https://www.googleapis.com/auth/drive.readonly`
- [ ] Добавить область: `https://www.googleapis.com/auth/drive.metadata.readonly`
- [ ] Добавить область: `https://www.googleapis.com/auth/fitness.activity.read`
- [ ] Добавить область: `https://www.googleapis.com/auth/fitness.body.read`
- [ ] Добавить область: `https://www.googleapis.com/auth/fitness.heart_rate.read`
- [ ] Добавить область: `https://www.googleapis.com/auth/fitness.sleep.read`

## ✅ Шаг 5: Создание учетных данных
- [ ] Создать "ID клиента OAuth 2.0"
- [ ] Тип: Веб-приложение
- [ ] Название: "Voit Bot"
- [ ] Добавить URI перенаправления: `http://localhost:8000/auth/google/callback`
- [ ] Скопировать Client ID и Client Secret

## ✅ Шаг 6: Настройка переменных окружения
- [ ] Создать файл `.env` из `env.example`
- [ ] Добавить `GOOGLE_CLIENT_ID`
- [ ] Добавить `GOOGLE_CLIENT_SECRET`
- [ ] Проверить `GOOGLE_REDIRECT_URI`

## ✅ Шаг 7: Тестирование
- [ ] Установить зависимости: `pip install -r requirements.txt`
- [ ] Проверить конфигурацию: `python -c "from app.config import settings; print(settings.google_client_id)"`
- [ ] Запустить бота: `python -m app.bot`
- [ ] Протестировать авторизацию Google

## ✅ Шаг 8: Продакшен (опционально)
- [ ] Обновить URI перенаправления на продакшен домен
- [ ] Удалить localhost URI
- [ ] Отправить экран согласия на проверку Google
- [ ] Обновить переменные окружения

## 🔍 Проверка настроек

### В Google Cloud Console:
- [ ] Проект активен
- [ ] API включены
- [ ] OAuth экран настроен
- [ ] Учетные данные созданы
- [ ] URI перенаправления корректны

### В коде:
- [ ] Client ID в .env файле
- [ ] Client Secret в .env файле
- [ ] Redirect URI в .env файле
- [ ] .env файл добавлен в .gitignore

### Тестирование:
- [ ] Бот запускается без ошибок
- [ ] Google авторизация работает
- [ ] Получение данных из Google Fit/Drive работает
- [ ] Логи показывают успешные запросы

## 🚨 Частые ошибки

### redirect_uri_mismatch
- Проверить точное совпадение URI в Google Console и коде
- Убрать лишние пробелы
- Проверить протокол (http/https)

### invalid_client
- Проверить правильность Client ID
- Убедиться, что проект активен
- Проверить, что API включены

### access_denied
- Проверить области в экране согласия OAuth
- Убедиться, что тестовые пользователи добавлены

## 📱 Настройка Google Fit на устройстве
- [ ] Установить Google Fit приложение
- [ ] Войти в Google аккаунт
- [ ] Разрешить доступ к данным активности
- [ ] Включить синхронизацию шагов, калорий, сна, пульса, веса

## 🔐 Безопасность
- [ ] .env файл не добавлен в Git
- [ ] Client Secret защищен
- [ ] Используются минимальные области доступа
- [ ] Настроены уведомления о подозрительной активности

## 📊 Мониторинг
- [ ] Проверить квоты API
- [ ] Настроить уведомления при 80% и 95% использовании
- [ ] Регулярно проверять логи
- [ ] Отслеживать использование API

---

**Готово!** 🎉
После выполнения всех пунктов ваш бот должен успешно интегрироваться с Google сервисами.
