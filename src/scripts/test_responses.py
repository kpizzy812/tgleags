#!/usr/bin/env python3
"""
Тестовый скрипт для проверки качества генерации ответов
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую папку проекта в Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.core.response_generator import ResponseGenerator
    from src.database.database import MessageBatch
    from src.database.models import Message
    from src.config.settings import character_settings
    from src.utils.helpers import setup_logging
    from loguru import logger
    from datetime import datetime
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Убедитесь, что файл запускается из корня проекта")
    sys.exit(1)


async def test_response_generation():
    """Тест генерации ответов с новой биографией Стаса"""
    setup_logging()
    
    print("🧪 Тестирование генерации ответов с биографией Стаса...")
    print(f"👤 Персонаж: {character_settings.name}, {character_settings.age} лет, {character_settings.occupation}")
    print("-" * 80)
    
    try:
        # Создаем генератор ответов
        generator = ResponseGenerator()
        
        # Тестовые сообщения для проверки
        test_scenarios = [
            {
                "name": "Знакомство",
                "messages": ["Привет! Как дела?"],
                "expected": "Короткий ответ + встречный вопрос"
            },
            {
                "name": "Вопрос о работе",
                "messages": ["Кем работаешь?"],
                "expected": "Рассказ о трейдинге + вопрос о её работе"
            },
            {
                "name": "Интерес к криптовалютам",
                "messages": ["Интересно! А что такое трейдинг?"],
                "expected": "Объяснение + встречный вопрос"
            },
            {
                "name": "Серия сообщений",
                "messages": ["Ого!", "Круто звучит!", "А рисково?"],
                "expected": "Ответ на всю серию + вопрос"
            },
            {
                "name": "Личный вопрос",
                "messages": ["А ты откуда родом?"],
                "expected": "Рассказ о Греции и международном опыте"
            },
            {
                "name": "Свободное время",
                "messages": ["А свободное время как проводишь?"],
                "expected": "Рассказ об интересах + встречный вопрос"
            }
        ]
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n{i}. 📝 Тест: {scenario['name']}")
            print(f"   Входящее: {' | '.join(scenario['messages'])}")
            print(f"   Ожидается: {scenario['expected']}")
            
            # Создаем фейковые сообщения для тестирования
            fake_messages = []
            for msg_text in scenario['messages']:
                fake_message = Message(
                    chat_id=999,  # Фейковый ID
                    text=msg_text,
                    is_from_ai=False,
                    created_at=datetime.utcnow()
                )
                fake_messages.append(fake_message)
            
            # Создаем пакет сообщений
            message_batch = MessageBatch(fake_messages)
            
            # Генерируем ответ
            try:
                response = await generator.generate_response_for_batch(999, message_batch)
                
                if response:
                    print(f"   ✅ Ответ: {response}")
                    
                    # Анализируем качество
                    analysis = []
                    if len(response.split('.')) <= 2:
                        analysis.append("✅ Короткий")
                    else:
                        analysis.append("❌ Слишком длинный")
                    
                    if '?' in response:
                        analysis.append("✅ Есть вопрос")
                    else:
                        analysis.append("⚠️ Нет встречного вопроса")
                    
                    if any(word in response.lower() for word in ['трейдинг', 'криптовалют', 'крипт']):
                        analysis.append("✅ Упоминает работу")
                    
                    print(f"   📊 Анализ: {' | '.join(analysis)}")
                else:
                    print(f"   ❌ Не удалось сгенерировать ответ")
                    
            except Exception as e:
                print(f"   ❌ Ошибка генерации: {e}")
            
            print("-" * 60)
        
        # Проверка настроек персонажа
        print(f"\n📋 Проверка настроек персонажа:")
        print(f"   Имя: {character_settings.name}")
        print(f"   Возраст: {character_settings.age}")
        print(f"   Профессия: {character_settings.occupation}")
        print(f"   Интересы: {', '.join(character_settings.interests[:3])}...")
        
        print(f"\n📖 Биография (первые 100 символов):")
        print(f"   {character_settings.background_story[:100]}...")
        
        print(f"\n💼 Детали работы:")
        work_details = character_settings.work_details
        print(f"   Тип: {work_details.get('company_type', 'не указан')}")
        print(f"   Опыт: {work_details.get('career_start', 'не указан')}")
        
        print(f"\n🎯 Системный промпт (первые 200 символов):")
        print(f"   {character_settings.system_prompt[:200]}...")
        
        print(f"\n✅ Тестирование завершено!")
        print(f"💡 Если ответы выглядят реалистично - можно запускать на реальных диалогах")
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция"""
    print("🚀 Запуск тестирования качества ответов...")
    print(f"📁 Текущая директория: {os.getcwd()}")
    
    await test_response_generation()


if __name__ == "__main__":
    asyncio.run(main())