#!/usr/bin/env python3
"""
Скрипт для проверки настройки проекта Telegram AI Companion
"""
import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Проверка версии Python"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Требуется Python 3.8 или выше")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_env_file():
    """Проверка .env файла"""
    if not os.path.exists('.env'):
        print("❌ Файл .env не найден")
        print("💡 Скопируйте .env.example в .env и заполните настройки:")
        print("   cp .env.example .env")
        return False
    print("✅ Файл .env найден")
    return True

def check_env_variables():
    """Проверка переменных окружения"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        required_vars = [
            'TELEGRAM_API_ID',
            'TELEGRAM_API_HASH', 
            'TELEGRAM_PHONE',
            'OPENAI_API_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ Не заполнены переменные: {', '.join(missing_vars)}")
            return False
        
        print("✅ Все необходимые переменные окружения заполнены")
        return True
        
    except ImportError:
        print("❌ Модуль python-dotenv не установлен")
        return False

def check_dependencies():
    """Проверка зависимостей"""
    required_packages = [
        'telethon',
        'openai', 
        'loguru',
        'pydantic',
        'sqlalchemy',
        'click',
        'python-dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Не установлены пакеты: {', '.join(missing_packages)}")
        print("💡 Установите зависимости:")
        print("   pip install -r requirements.txt")
        return False
    
    print("✅ Все зависимости установлены")
    return True

def check_project_structure():
    """Проверка структуры проекта"""
    required_dirs = [
        'src/core',
        'src/config', 
        'src/database',
        'src/utils',
        'src/cli',
        'src/scripts'
    ]
    
    required_files = [
        'src/core/telegram_client.py',
        'src/core/response_generator.py',
        'src/core/message_monitor.py',
        'src/config/settings.py',
        'src/database/models.py',
        'src/database/database.py',
        'src/cli/main.py',
        'requirements.txt'
    ]
    
    missing_items = []
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            missing_items.append(f"Директория: {dir_path}")
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_items.append(f"Файл: {file_path}")
    
    if missing_items:
        print("❌ Отсутствуют файлы/директории:")
        for item in missing_items:
            print(f"   {item}")
        return False
    
    print("✅ Структура проекта корректна")
    return True

def check_imports():
    """Проверка импортов"""
    try:
        sys.path.insert(0, '.')
        
        from src.config.settings import settings, character_settings
        from src.database.database import db_manager
        from src.core.telegram_client import TelegramAIClient
        from src.core.response_generator import ResponseGenerator
        from src.cli.main import cli
        
        print("✅ Все модули импортируются корректно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка импорта модулей: {e}")
        return False

def main():
    """Основная функция проверки"""
    print("🔧 Проверка настройки Telegram AI Companion...")
    print("=" * 60)
    
    checks = [
        ("Python версия", check_python_version),
        ("Структура проекта", check_project_structure),
        ("Зависимости", check_dependencies),
        (".env файл", check_env_file),
        ("Переменные окружения", check_env_variables),
        ("Импорты модулей", check_imports)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        print(f"\n📋 {name}:")
        if check_func():
            passed += 1
        else:
            print(f"   Проверка не пройдена!")
    
    print("\n" + "=" * 60)
    print(f"📊 Результат: {passed}/{total} проверок пройдено")
    
    if passed == total:
        print("🎉 Все проверки пройдены! Проект готов к запуску.")
        print("\n💡 Следующие шаги:")
        print("1. python src/scripts/test_responses.py  # Тест генерации ответов")
        print("2. python -m src.cli.main test           # Тест подключений")
        print("3. python -m src.cli.main start          # Запуск мониторинга")
    else:
        print("❌ Необходимо исправить проблемы перед запуском.")
        
        if not os.path.exists('.env'):
            print("\n🚀 Быстрая настройка:")
            print("1. cp .env.example .env")
            print("2. Отредактируйте .env файл (API ключи, номер телефона)")
            print("3. pip install -r requirements.txt")
            print("4. python check_setup.py")

if __name__ == "__main__":
    main()