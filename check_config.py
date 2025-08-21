#!/usr/bin/env python3
"""
Скрипт для проверки конфигурации Google credentials.
"""

import os
from pathlib import Path

def check_env_file():
    """Проверяем файл .env"""
    print("🔍 Проверка файла .env")
    
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ Файл .env не найден!")
        print("💡 Создайте файл .env на основе env.example")
        return False
    
    print("✅ Файл .env найден")
    
    # Читаем содержимое
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Проверяем Google credentials
    google_client_id = None
    google_client_secret = None
    google_redirect_uri = None
    
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('GOOGLE_CLIENT_ID='):
            google_client_id = line.split('=', 1)[1]
        elif line.startswith('GOOGLE_CLIENT_SECRET='):
            google_client_secret = line.split('=', 1)[1]
        elif line.startswith('GOOGLE_REDIRECT_URI='):
            google_redirect_uri = line.split('=', 1)[1]
    
    print(f"\n📱 Google Credentials:")
    print(f"   Client ID: {'✅ Установлен' if google_client_id and google_client_id != 'your_google_client_id' else '❌ НЕ УСТАНОВЛЕН'}")
    print(f"   Client Secret: {'✅ Установлен' if google_client_secret and google_client_secret != 'your_google_client_secret' else '❌ НЕ УСТАНОВЛЕН'}")
    print(f"   Redirect URI: {google_redirect_uri or '❌ НЕ УСТАНОВЛЕН'}")
    
    if not google_client_id or google_client_id == 'your_google_client_id':
        print("\n🚨 ПРОБЛЕМА: Google Client ID не настроен!")
        print("💡 Заполните GOOGLE_CLIENT_ID в файле .env")
        return False
    
    if not google_client_secret or google_client_secret == 'your_google_client_secret':
        print("\n🚨 ПРОБЛЕМА: Google Client Secret не настроен!")
        print("💡 Заполните GOOGLE_CLIENT_SECRET в файле .env")
        return False
    
    print("\n✅ Google credentials настроены правильно!")
    return True

def check_google_cloud_setup():
    """Проверяем настройки Google Cloud Console"""
    print("\n🔍 Проверка настроек Google Cloud Console")
    print("📋 Убедитесь, что выполнены следующие шаги:")
    print("   1. ✅ Создан проект в Google Cloud Console")
    print("   2. ✅ Включен Google Fit API")
    print("   3. ✅ Включен Google Drive API")
    print("   4. ✅ Созданы OAuth 2.0 credentials")
    print("   5. ✅ Добавлен redirect URI: http://localhost:8000/auth/google/callback")
    
    print("\n🔗 Ссылки для проверки:")
    print("   • Google Cloud Console: https://console.cloud.google.com/")
    print("   • APIs & Services → Library: https://console.cloud.google.com/apis/library")
    print("   • APIs & Services → Credentials: https://console.cloud.google.com/apis/credentials")

def main():
    """Основная функция"""
    print("🚀 Проверка конфигурации Health Connect")
    print("=" * 50)
    
    # Проверяем .env файл
    env_ok = check_env_file()
    
    # Проверяем Google Cloud Console
    check_google_cloud_setup()
    
    print("\n" + "=" * 50)
    if env_ok:
        print("🎉 Конфигурация выглядит правильно!")
        print("💡 Если проблема остается, проверьте настройки Google Cloud Console")
    else:
        print("❌ Обнаружены проблемы с конфигурацией!")
        print("🔧 Исправьте их и запустите проверку снова")
    
    print("\n📚 Подробная инструкция: HEALTH_CONNECT_TROUBLESHOOTING.md")

if __name__ == "__main__":
    main()
