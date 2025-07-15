#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к Telegram
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую папку проекта в Python path (на 2 уровня выше)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.core.telegram_client import TelegramAIClient
    from src.config.settings import settings
    from src.utils.helpers import setup_logging
    from loguru import logger
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Убедитесь, что файл запускается из корня проекта")
    print(f"Текущая папка: {os.getcwd()}")
    print(f"Путь к скрипту: {__file__}")
    print(f"Project root: {project_root}")
    sys.exit(1)


async def test_telegram_connection():
    """Тест подключения к Telegram"""
    setup_logging()
    
    logger.info("🧪 Начинаем тест подключения к Telegram...")
    
    try:
        # Создаем клиент
        client = TelegramAIClient()
        
        # Пробуем инициализировать
        logger.info("1️⃣ Инициализация клиента...")
        if not await client.initialize():
            logger.error("❌ Не удалось инициализировать клиент")
            return False
        
        logger.info("✅ Клиент инициализирован успешно")
        
        # Пробуем подключиться
        logger.info("2️⃣ Подключение к Telegram...")
        if not await client.connect():
            logger.error("❌ Не удалось подключиться к Telegram")
            return False
        
        logger.info("✅ Подключение к Telegram успешно")
        
        # Получаем информацию о себе
        logger.info("3️⃣ Получение информации о пользователе...")
        me = await client.client.get_me()
        if me:
            logger.info(f"✅ Подключен как: {me.first_name} (@{me.username}) ID: {me.id}")
        else:
            logger.warning("⚠️ Не удалось получить информацию о пользователе")
        
        # Получаем список диалогов
        logger.info("4️⃣ Получение списка диалогов...")
        dialogs = await client.get_dialogs()
        logger.info(f"✅ Найдено диалогов: {len(dialogs)}")
        
        if dialogs:
            logger.info("📋 Первые 3 диалога:")
            for i, dialog in enumerate(dialogs[:3], 1):
                name = dialog.get('name', 'Без имени')
                username = f"@{dialog['username']}" if dialog.get('username') else ""
                logger.info(f"   {i}. {name} {username} (ID: {dialog['id']})")
        
        # Отключаемся
        logger.info("5️⃣ Отключение...")
        await client.stop_monitoring()
        
        logger.info("🎉 Все тесты пройдены успешно!")
        return True
        
    except Exception as e:
        logger.error(f"💥 Ошибка во время тестирования: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def main():
    """Главная функция"""
    print("🚀 Запуск тестирования Telegram AI Companion...")
    print(f"📁 Текущая директория: {os.getcwd()}")
    
    # Проверяем конфигурацию
    print("📋 Проверка конфигурации...")
    
    try:
        print(f"   API ID: {settings.telegram_api_id}")
        print(f"   API Hash: {'*' * len(str(settings.telegram_api_hash))}")
        print(f"   Phone: {settings.telegram_phone}")
        print(f"   OpenAI Model: {settings.openai_model}")
        
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            print("❌ Не настроены Telegram API параметры в .env файле")
            return
        
        if not settings.openai_api_key:
            print("❌ Не настроен OpenAI API ключ в .env файле")
            return
    except Exception as e:
        print(f"❌ Ошибка чтения конфигурации: {e}")
        print("Убедитесь, что файл .env настроен правильно")
        return
    
    # Запускаем тест
    success = await test_telegram_connection()
    
    if success:
        print("✅ Telegram AI Companion готов к работе!")
        print("💡 Для запуска полного мониторинга используйте:")
        print("   python3 -m src.cli.main start")
    else:
        print("❌ Обнаружены проблемы. Проверьте настройки и повторите тест.")


if __name__ == "__main__":
    asyncio.run(main())