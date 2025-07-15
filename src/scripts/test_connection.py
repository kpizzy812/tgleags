#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к Telegram
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from src.core.telegram_client import TelegramAIClient
from src.config.settings import settings
from src.utils.helpers import setup_logging
from loguru import logger


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
    logger.info("🚀 Запуск тестирования Telegram AI Companion...")
    
    # Проверяем конфигурацию
    logger.info("📋 Проверка конфигурации...")
    logger.info(f"   API ID: {settings.telegram_api_id}")
    logger.info(f"   API Hash: {'*' * len(settings.telegram_api_hash)}")
    logger.info(f"   Phone: {settings.telegram_phone}")
    logger.info(f"   OpenAI Model: {settings.openai_model}")
    
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        logger.error("❌ Не настроены Telegram API параметры в .env файле")
        return
    
    if not settings.openai_api_key:
        logger.error("❌ Не настроен OpenAI API ключ в .env файле")
        return
    
    # Запускаем тест
    success = await test_telegram_connection()
    
    if success:
        logger.info("✅ Telegram AI Companion готов к работе!")
        logger.info("💡 Для запуска полного мониторинга используйте:")
        logger.info("   python -m src.cli.main start")
    else:
        logger.error("❌ Обнаружены проблемы. Проверьте настройки и повторите тест.")


if __name__ == "__main__":
    asyncio.run(main())