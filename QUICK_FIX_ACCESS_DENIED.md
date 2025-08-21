# 🚨 Быстрое исправление ошибки "Доступ заблокирован"

## ⚡ Проблема
При нажатии "Подключить Health Connect" выходит ошибка: **"Доступ заблокирован: ошибка авторизации"**

## 🔧 Быстрое решение (5 минут)

### Шаг 1: Проверьте файл .env
```bash
# Запустите проверку конфигурации:
python check_config.py
```

### Шаг 2: Если .env не настроен
1. Откройте файл `.env`
2. Замените строки:
   ```env
   # Было:
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   
   # Должно быть:
   GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-abcdefghijklmnopqrstuvwxyz
   ```

### Шаг 3: Перезапустите бота
```bash
# Остановите бота (Ctrl+C)
# Затем запустите снова:
python -m app.bot
```

## 🆘 Если .env пустой

### Вариант 1: Настройка Google Cloud Console
1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте проект и включите Google Fit API
3. Создайте OAuth 2.0 credentials
4. Заполните .env файл

### Вариант 2: Используйте Google Drive (проще)
1. В боте: `Здоровье → 🔗 Интеграции → 📁 Google Drive`
2. Установите Health Sync на телефон
3. Настройте экспорт данных

## ✅ Проверка исправления

После исправления:
1. ✅ Бот запускается без ошибок
2. ✅ В меню "🔗 Интеграции" видно Health Connect
3. ✅ При нажатии "Подключить Health Connect" открывается Google авторизация

## 🔗 Полезные ссылки

- **Подробная инструкция**: [HEALTH_CONNECT_TROUBLESHOOTING.md](HEALTH_CONNECT_TROUBLESHOOTING.md)
- **Быстрый старт**: [HEALTH_CONNECT_QUICK_START.md](HEALTH_CONNECT_QUICK_START.md)
- **В боте**: `Здоровье → 🔗 Интеграции → 🔧 Настройка Google Cloud`

---

**Главное:** Не забудьте перезапустить бота после изменения .env файла! 🚀
