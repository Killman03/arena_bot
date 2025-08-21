# 🚨 Исправление ошибки "Доступ заблокирован" в Health Connect

## 🔍 Диагностика проблемы

**Ошибка:** "Доступ заблокирован: ошибка авторизации" при нажатии "Подключить Health Connect"

**Причины:**
1. ❌ Не настроен Google Cloud Console
2. ❌ Не включены нужные API
3. ❌ Неправильные OAuth credentials
4. ❌ Неверный redirect URI
5. ❌ Отсутствует файл `.env`

## 🛠️ Пошаговое решение

### Шаг 1: Настройка Google Cloud Console

#### 1.1 Создание проекта
1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Запомните **Project ID**

#### 1.2 Включение API
В разделе **"APIs & Services" → "Library"** включите:
- ✅ **Google Fit API**
- ✅ **Google Drive API** 
- ✅ **Google+ API** (если требуется)

#### 1.3 Создание OAuth 2.0 credentials
1. Перейдите в **"APIs & Services" → "Credentials"**
2. Нажмите **"Create Credentials" → "OAuth 2.0 Client IDs"**
3. Выберите тип: **"Web application"**
4. Добавьте **Authorized redirect URIs**:
   ```
   http://localhost:8000/auth/google/callback
   https://yourdomain.com/auth/google/callback  # если есть домен
   ```
5. Сохраните **Client ID** и **Client Secret**

### Шаг 2: Настройка переменных окружения

#### 2.1 Создание файла .env
```bash
# Скопируйте пример:
copy env.example .env
```

#### 2.2 Заполнение Google credentials
Откройте файл `.env` и заполните:
```env
# Google Fit Integration
GOOGLE_CLIENT_ID=your_actual_client_id_here
GOOGLE_CLIENT_SECRET=your_actual_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

**Важно:** Замените `your_actual_client_id_here` на реальный Client ID из Google Cloud Console

### Шаг 3: Перезапуск бота

После изменения `.env` файла **обязательно** перезапустите бота:

```bash
# Остановите бота (Ctrl+C)
# Затем запустите снова:
python -m app.bot
```

## 🧪 Проверка конфигурации

### Тест 1: Проверка переменных окружения
```bash
python -c "
from app.config import settings
print(f'Google Client ID: {settings.google_client_id}')
print(f'Google Client Secret: {settings.google_client_secret[:10]}...')
print(f'Redirect URI: {settings.google_redirect_uri}')
"
```

### Тест 2: Тест Health Connect сервиса
```bash
python test_health_connect.py
```

## 🚨 Частые ошибки и решения

### Ошибка 1: "No module named 'aiohttp'"
```bash
pip install aiohttp
```

### Ошибка 2: "Invalid client_id"
- Проверьте правильность Client ID в `.env`
- Убедитесь, что скопировали ID полностью

### Ошибка 3: "Redirect URI mismatch"
- Проверьте redirect URI в Google Cloud Console
- Убедитесь, что URI в `.env` совпадает с настроенным

### Ошибка 4: "API not enabled"
- Включите Google Fit API в Google Cloud Console
- Подождите несколько минут после включения

## 📱 Проверка на телефоне

### Android 14+ (Health Connect)
1. Откройте **Настройки → Здоровье**
2. Убедитесь, что видите **Health Connect**
3. Проверьте, что подключены нужные приложения

### Альтернативы (если Health Connect недоступен)
1. **Google Fit** - прямая интеграция
2. **Google Drive** - через Health Sync

## 🔧 Дополнительная диагностика

### Проверка логов бота
```bash
# Запустите бота с подробным логированием
python -m app.bot --log-level DEBUG
```

### Проверка Google Cloud Console
1. **APIs & Services → Dashboard** - проверьте включенные API
2. **APIs & Services → Credentials** - проверьте OAuth credentials
3. **APIs & Services → OAuth consent screen** - проверьте настройки

## ✅ Проверка успешности

После исправления:
1. ✅ Бот запускается без ошибок
2. ✅ В меню "🔗 Интеграции" видно Health Connect
3. ✅ При нажатии "Подключить Health Connect" открывается Google авторизация
4. ✅ После авторизации получаете код для бота
5. ✅ Команда `/health_connect_auth КОД` работает

## 🆘 Если ничего не помогает

1. **Проверьте интернет-соединение**
2. **Убедитесь, что Google Cloud Console доступен**
3. **Попробуйте другой браузер**
4. **Очистите кэш браузера**
5. **Проверьте, не блокирует ли антивирус**

## 📞 Поддержка

Если проблема остается:
1. Сделайте скриншот ошибки
2. Проверьте логи бота
3. Убедитесь, что выполнили все шаги
4. Обратитесь к разработчикам с подробным описанием

---

**Помните:** Health Connect требует Android 14+ и правильно настроенный Google Cloud Console!
