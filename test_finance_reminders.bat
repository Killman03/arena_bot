@echo off
echo 🧪 Тестирование финансовых уведомлений...

REM Try to find Python
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo ✅ Python найден
    python test_finance_reminders.py
    goto :end
)

python3 --version >nul 2>&1
if %errorlevel% == 0 (
    echo ✅ Python3 найден
    python3 test_finance_reminders.py
    goto :end
)

echo ❌ Python не найден
echo Попробуйте запустить команду в терминале PyCharm
pause

:end
echo Тестирование завершено
pause
