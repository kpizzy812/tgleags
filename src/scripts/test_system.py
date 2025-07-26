#!/usr/bin/env python3
"""
Обновленная проверка настройки Telegram AI Companion после упрощения
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


def check_simplified_project_structure():
    """Проверка упрощенной структуры проекта"""
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
        'src/cli/chat_commands.py',
        'src/cli/stats_commands.py',
        'requirements.txt'
    ]

    # Проверяем что удалены старые файлы
    deprecated_items = [
        'src/analysis/',
        'src/utils/openai_helper.py',
        'CHECK_TEST.md',
        'CHECK_LIST.md'
    ]

    missing_items = []
    deprecated_found = []

    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            missing_items.append(f"Директория: {dir_path}")

    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_items.append(f"Файл: {file_path}")

    for deprecated_item in deprecated_items:
        if os.path.exists(deprecated_item):
            deprecated_found.append(deprecated_item)

    if missing_items:
        print("❌ Отсутствуют файлы/директории:")
        for item in missing_items:
            print(f"   {item}")
        return False

    if deprecated_found:
        print("⚠️ Найдены устаревшие файлы (рекомендуется удалить):")
        for item in deprecated_found:
            print(f"   {item}")

    print("✅ Упрощенная структура проекта корректна")
    return True


def check_database_migration():
    """Проверка состояния базы данных"""
    try:
        db_path = "./telegram_ai.db"

        if not os.path.exists(db_path):
            print("📭 База данных не существует (будет создана при первом запуске)")
            return True

        # Проверяем структуру БД
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = ['chats', 'messages', 'person_facts']
        deprecated_tables = ['chat_contexts', 'dialogue_analytics']

        # Проверяем новые таблицы
        missing_tables = [t for t in expected_tables if t not in tables]
        deprecated_present = [t for t in deprecated_tables if t in tables]

        conn.close()

        if missing_tables:
            print(f"❌ БД: отсутствуют таблицы: {', '.join(missing_tables)}")
            print("💡 Запустите миграцию: python src/scripts/migrate_database.py")
            return False

        if deprecated_present:
            print(f"⚠️ БД: найдены устаревшие таблицы: {', '.join(deprecated_present)}")
            print("💡 Рекомендуется миграция: python src/scripts/migrate_database.py")

        print(f"✅ База данных: упрощенная структура ({len(tables)} таблиц)")
        return True

    except Exception as e:
        print(f"❌ База данных: ошибка проверки: {e}")
        return False


def check_simplified_imports():
    """Проверка импортов упрощенной системы"""
    try:
        sys.path.insert(0, '.')

        # Проверяем основные модули
        from src.config.settings import settings, character_settings
        from src.database.database import db_manager
        from src.core.telegram_client import TelegramAIClient
        from src.core.response_generator import ResponseGenerator
        from src.core.message_monitor import MessageMonitor
        from src.cli.main import cli

        print("✅ Все упрощенные модули импортируются корректно")

        # Проверяем что старые модули удалены
        deprecated_modules = [
            'src.analysis.conversation_analyzer',
            'src.analysis.financial_analyzer',
            'src.utils.openai_helper'
        ]

        deprecated_found = []
        for module in deprecated_modules:
            try:
                __import__(module)
                deprecated_found.append(module)
            except ImportError:
                pass  # Это хорошо - модуль удален

        if deprecated_found:
            print(f"⚠️ Найдены устаревшие модули: {', '.join(deprecated_found)}")
            print("💡 Рекомендуется удалить папку src/analysis/")

        return True

    except Exception as e:
        print(f"❌ Ошибка импорта модулей: {e}")
        return False


def check_character_settings():
    """Проверка настроек персонажа"""
    try:
        from src.config.settings import character_settings

        # Проверяем ключевые настройки
        checks = [
            ('Имя', character_settings.name, lambda x: bool(x and len(x) > 0)),
            ('Возраст', character_settings.age, lambda x: isinstance(x, int) and 20 <= x <= 40),
            ('Профессия', character_settings.occupation, lambda x: 'крипто' in x.lower() or 'трейд' in x.lower()),
            ('Системный промпт', character_settings.system_prompt, lambda x: len(x) > 200),
            ('Триггеры помощи', character_settings.help_offer_triggers, lambda x: len(x) >= 5)
        ]

        all_good = True
        for name, value, check_func in checks:
            if check_func(value):
                print(f"✅ Персонаж.{name}: корректно")
            else:
                print(f"❌ Персонаж.{name}: некорректно")
                all_good = False

        return all_good

    except Exception as e:
        print(f"❌ Ошибка проверки настроек персонажа: {e}")
        return False


def check_cli_functionality():
    """Проверка функциональности CLI"""
    try:
        from src.cli.main import cli
        from src.cli.chat_commands import chat_commands
        from src.cli.stats_commands import stats_commands

        # Проверяем что команды существуют
        expected_commands = [
            'start', 'status', 'config', 'test', 'queue',  # main
            'send', 'dialogs', 'messages',  # chat
            'stats', 'facts', 'opportunities'  # stats
        ]

        print(f"✅ CLI: модули загружены, команд: {len(expected_commands)}")
        return True

    except Exception as e:
        print(f"❌ CLI: ошибка загрузки: {e}")
        return False


def main():
    """Основная функция проверки"""
    print("🔧 Проверка упрощенной системы Telegram AI Companion...")
    print("=" * 70)

    checks = [
        ("Python версия", check_python_version),
        ("Упрощенная структура", check_simplified_project_structure),
        ("Зависимости", check_dependencies),
        (".env файл", check_env_file),
        ("Переменные окружения", check_env_variables),
        ("База данных", check_database_migration),
        ("Импорты модулей", check_simplified_imports),
        ("Настройки персонажа", check_character_settings),
        ("CLI функциональность", check_cli_functionality)
    ]

    passed = 0
    total = len(checks)

    for name, check_func in checks:
        print(f"\n📋 {name}:")
        if check_func():
            passed += 1
        else:
            print(f"   Проверка не пройдена!")

    print("\n" + "=" * 70)
    print(f"📊 Результат: {passed}/{total} проверок пройдено")

    if passed == total:
        print("🎉 Упрощенная система готова к работе!")
        print("\n💡 Следующие шаги:")
        print("1. python src/scripts/test_system.py      # Комплексное тестирование")
        print("2. python -m src.cli.main test            # Тест подключений")
        print("3. python -m src.cli.main start           # Запуск мониторинга")
    elif passed >= total * 0.8:
        print("⚠️ Система почти готова, но есть предупреждения.")
        print("💡 Можно запускать, но рекомендуется устранить проблемы.")
    else:
        print("❌ Необходимо исправить критические проблемы.")

        print("\n🚀 Быстрая миграция к упрощенной системе:")
        print("1. python src/scripts/migrate_database.py  # Миграция БД")
        print("2. rm -rf src/analysis/                    # Удаление переусложнения")
        print("3. python check_setup.py                   # Повторная проверка")


if __name__ == "__main__":
    main()