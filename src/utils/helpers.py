"""
Вспомогательные функции
"""
import asyncio
import random
import re
from typing import List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from ..config.settings import settings


def setup_logging():
    """Настройка логирования"""
    logger.remove()  # Удаляем стандартный обработчик
    
    # Консольный вывод
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # Файловый вывод
    logger.add(
        sink=settings.log_file,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="1 day",
        retention="7 days",
        compression="zip"
    )


def get_random_delay(min_delay: int = None, max_delay: int = None) -> int:
    """Получить случайную задержку для имитации человеческого поведения"""
    min_delay = min_delay or settings.min_response_delay
    max_delay = max_delay or settings.max_response_delay
    return random.randint(min_delay, max_delay)


def clean_text(text: str) -> str:
    """Очистка текста от лишних символов"""
    if not text:
        return ""
    
    # Удаляем лишние пробелы и переносы
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Удаляем эмодзи для анализа (оставляем только текст)
    text_clean = re.sub(r'[^\w\s\.,!?;:\-()]+', '', text)
    
    return text_clean


def extract_keywords(text: str) -> List[str]:
    """Извлечение ключевых слов из текста"""
    if not text:
        return []
    
    # Простое извлечение слов (можно улучшить с помощью NLP)
    words = re.findall(r'\b\w{3,}\b', text.lower())
    
    # Исключаем стоп-слова
    stop_words = {
        'это', 'что', 'как', 'где', 'когда', 'почему', 'который', 'которая', 'которое',
        'для', 'или', 'при', 'без', 'над', 'под', 'про', 'через', 'после', 'перед',
        'тоже', 'также', 'еще', 'уже', 'только', 'даже', 'если', 'чтобы', 'потому',
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her',
        'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its'
    }
    
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    return list(set(keywords))  # Убираем дубликаты


def is_question(text: str) -> bool:
    """Проверка, является ли сообщение вопросом"""
    if not text:
        return False
    
    # Простая проверка на вопросительные слова и знаки
    question_words = ['что', 'как', 'где', 'когда', 'почему', 'зачем', 'кто', 'чей', 'какой', 'сколько']
    question_patterns = ['?', 'что делаешь', 'как дела', 'что нового']
    
    text_lower = text.lower()
    
    return (
        '?' in text or
        any(word in text_lower for word in question_words) or
        any(pattern in text_lower for pattern in question_patterns)
    )


def format_chat_history_for_ai(messages: List[Dict[str, Any]]) -> str:
    """Форматирование истории чата для ИИ"""
    formatted_messages = []
    
    for msg in messages[-10:]:  # Берем последние 10 сообщений
        role = "assistant" if msg.get('is_from_ai') else "user"
        text = msg.get('text', '')
        
        if text:
            formatted_messages.append(f"{role}: {text}")
    
    return "\n".join(formatted_messages)


def should_respond_to_message(text: str, last_ai_message_time: datetime = None) -> bool:
    """Определить, нужно ли отвечать на сообщение"""
    if not text:
        return False
    
    # Не отвечаем слишком часто
    if last_ai_message_time:
        time_since_last = datetime.utcnow() - last_ai_message_time
        if time_since_last.total_seconds() < 30:  # Минимум 30 секунд между ответами
            return False
    
    # Простые правила для определения необходимости ответа
    text_lower = text.lower()
    
    # Всегда отвечаем на вопросы
    if is_question(text):
        return True
    
    # Отвечаем на приветствия
    greetings = ['привет', 'приветик', 'здравствуй', 'добрый', 'хай', 'hello', 'hi']
    if any(greeting in text_lower for greeting in greetings):
        return True
    
    # Отвечаем на эмоциональные сообщения
    emotional_words = ['спасибо', 'классно', 'супер', 'отлично', 'ужасно', 'плохо', 'грустно']
    if any(word in text_lower for word in emotional_words):
        return True
    
    # В остальных случаях отвечаем с вероятностью 70%
    return random.random() < 0.7


async def simulate_typing(duration: int = None):
    """Имитация печатания (задержка)"""
    duration = duration or settings.typing_duration
    await asyncio.sleep(duration)


def get_time_based_greeting() -> str:
    """Получить приветствие в зависимости от времени суток"""
    current_hour = datetime.now().hour
    
    if 6 <= current_hour < 12:
        return "Доброе утро"
    elif 12 <= current_hour < 18:
        return "Добрый день"
    elif 18 <= current_hour < 23:
        return "Добрый вечер"
    else:
        return "Привет"


def add_random_typo(text: str, probability: float = 0.05) -> str:
    """Добавить случайную опечатку для имитации человеческого поведения"""
    if random.random() > probability or len(text) < 5:
        return text
    
    # Простые опечатки - замена соседних букв
    typo_map = {
        'а': 'о', 'о': 'а', 'е': 'и', 'и': 'е',
        'т': 'р', 'р': 'т', 'н': 'м', 'м': 'н'
    }
    
    text_list = list(text.lower())
    for i, char in enumerate(text_list):
        if char in typo_map and random.random() < 0.3:
            text_list[i] = typo_map[char]
            break
    
    return ''.join(text_list)