# PowerShell скрипт для тестирования финансовых уведомлений

Write-Host "🧪 Тестирование финансовых уведомлений..." -ForegroundColor Green

# Проверяем наличие Python
$pythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    $pythonPath = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $pythonPath) {
    Write-Host "❌ Python не найден в PATH" -ForegroundColor Red
    Write-Host "Попробуйте запустить команду в терминале PyCharm или установить Python" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Python найден: $($pythonPath.Source)" -ForegroundColor Green

# Запускаем тестовый скрипт
Write-Host "📤 Запускаем тестовый скрипт..." -ForegroundColor Cyan
& $pythonPath.Source "test_finance_reminders.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Тестирование завершено успешно!" -ForegroundColor Green
} else {
    Write-Host "❌ Тестирование завершилось с ошибкой" -ForegroundColor Red
}
