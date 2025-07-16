"""
Вспомогательные функции для Telegram AI Companion
"""
import random
import re
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger


def setup_logging():
    """Настройка логирования"""
    from src.config.settings import settings
    
    # Создаем директорию для логов
    os.makedirs("logs", exist_ok=True)
    
    # Убираем старые обработчики
    logger.remove()
    
    # Консольный вывод
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # Файловый вывод
    logger.add(
        sink=settings.log_file,
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )
    
    logger.info("Логирование настроено")


def get_random_delay(min_seconds: int = 5, max_seconds: int = 30) -> int:
    """Получить случайную задержку"""
    return random.randint(min_seconds, max_seconds)


def get_smart_delay(current_hour: int, emotion: str = 'neutral', relationship_stage: str = 'initial') -> int:
    """Умная задержка в зависимости от времени и контекста"""
    from src.config.settings import settings
    
    base_delay = settings.min_response_delay
    max_delay = settings.max_response_delay
    
    # Корректировка по времени суток
    if 0 <= current_hour < 7:      # Ночь
        time_multiplier = 3.0
    elif 7 <= current_hour < 9:    # Раннее утро
        time_multiplier = 2.0
    elif 9 <= current_hour < 18:   # Рабочий день
        time_multiplier = 1.0
    elif 18 <= current_hour < 22:  # Вечер
        time_multiplier = 0.8
    else:                          # Поздний вечер
        time_multiplier = 1.5
    
    # Корректировка по эмоции
    emotion_multipliers = {
        'негативный': 0.5,   # Быстро отвечаем на негатив
        'позитивный': 1.2,   # Чуть медленнее на позитив
        'нейтральный': 1.0,  # Обычно
        'любопытный': 0.7,   # Быстро на любопытство
        'флиртующий': 0.6    # Быстро на флирт
    }
    
    # Корректировка по стадии отношений
    stage_multipliers = {
        'initial': 2.0,      # В начале медленнее
        'getting_acquainted': 1.5,   # Знакомимся
        'personal': 1.0,     # Личные темы
        'ready_to_meet': 0.8 # Готовы к встрече
    }
    
    # Финальный расчет
    delay = base_delay * time_multiplier
    delay *= emotion_multipliers.get(emotion, 1.0)
    delay *= stage_multipliers.get(relationship_stage, 1.0)
    
    # Добавляем случайность
    randomness = random.uniform(0.8, 1.2)
    delay *= randomness
    
    # Ограничиваем диапазон
    delay = max(base_delay, min(int(delay), max_delay))
    
    return delay


def clean_text(text: str) -> str:
    """Очистка текста от лишних символов"""
    if not text:
        return ""
    
    # Убираем лишние пробелы
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Убираем некорректные символы
    text = re.sub(r'[^\w\s.,!?():-]', '', text)
    
    return text


def extract_keywords(text: str) -> List[str]:
    """Извлечение ключевых слов из текста"""
    if not text:
        return []
    
    text = text.lower()
    
    # Стоп-слова
    stop_words = {'и', 'в', 'на', 'с', 'по', 'для', 'не', 'что', 'это', 'как', 'а', 'но', 'или'}
    
    # Извлекаем слова
    words = re.findall(r'\b\w+\b', text)
    keywords = [word for word in words if len(word) > 2 and word not in stop_words]
    
    return keywords


def is_question(text: str) -> bool:
    """Проверка, является ли текст вопросом"""
    if not text:
        return False
    
    # Явные признаки вопроса
    if '?' in text:
        return True
    
    # Вопросительные слова
    question_words = ['как', 'что', 'где', 'когда', 'почему', 'зачем', 'кто', 'какой', 'какая', 'какие']
    text_lower = text.lower()
    
    return any(word in text_lower for word in question_words)


def get_time_based_greeting() -> str:
    """Получить приветствие в зависимости от времени"""
    current_hour = datetime.now().hour
    
    if 5 <= current_hour < 12:
        return "Доброе утро"
    elif 12 <= current_hour < 18:
        return "Добрый день"
    elif 18 <= current_hour < 23:
        return "Добрый вечер"
    else:
        return "Доброй ночи"


def add_random_typo(text: str) -> str:
    """Добавление случайной опечатки для реалистичности"""
    if len(text) < 10 or random.random() > 0.3:  # 30% шанс
        return text
    
    words = text.split()
    if len(words) < 2:
        return text
    
    # Выбираем случайное слово для изменения
    word_index = random.randint(0, len(words) - 1)
    word = words[word_index]
    
    if len(word) < 3:
        return text
    
    # Типы опечаток
    typo_type = random.choice(['missing_letter', 'extra_letter', 'wrong_letter'])
    
    if typo_type == 'missing_letter' and len(word) > 3:
        # Убираем букву
        pos = random.randint(1, len(word) - 2)
        new_word = word[:pos] + word[pos+1:]
    elif typo_type == 'extra_letter':
        # Добавляем букву
        pos = random.randint(1, len(word) - 1)
        letter = random.choice('абвгдежзийклмнопрстуфхцчшщэюя')
        new_word = word[:pos] + letter + word[pos:]
    else:
        # Заменяем букву
        pos = random.randint(1, len(word) - 2)
        letter = random.choice('абвгдежзийклмнопрстуфхцчшщэюя')
        new_word = word[:pos] + letter + word[pos+1:]
    
    words[word_index] = new_word
    return ' '.join(words)


def format_chat_history_for_ai(messages: List[Dict[str, Any]], limit: int = 10) -> str:
    """Форматирование истории чата для ИИ"""
    if not messages:
        return "Начало диалога"
    
    # Берем последние сообщения
    recent_messages = messages[-limit:]
    
    formatted_lines = []
    for msg in recent_messages:
        role = "ИИ" if msg.get('is_from_ai', False) else "Пользователь"
        timestamp = msg.get('created_at', datetime.now()).strftime("%H:%M")
        text = msg.get('text', '')
        
        if text:
            formatted_lines.append(f"[{timestamp}] {role}: {text}")
    
    return "\n".join(formatted_lines)


class MessagePatternAnalyzer:
    """Анализатор паттернов сообщений"""
    
    @staticmethod
    def detect_spam_pattern(messages: List[Dict], time_window: int = 60) -> bool:
        """Определить спам-паттерн в сообщениях"""
        if len(messages) < 5:
            return False
        
        # Проверяем частоту сообщений
        recent_messages = [
            msg for msg in messages 
            if (datetime.utcnow() - msg.get('created_at', datetime.utcnow())).seconds < time_window
        ]
        
        if len(recent_messages) > 10:  # Больше 10 сообщений в минуту
            return True
        
        # Проверяем повторяющийся текст
        texts = [msg.get('text', '').lower().strip() for msg in recent_messages]
        unique_texts = set(texts)
        
        if len(unique_texts) < len(texts) / 2:  # Больше половины повторяющихся
            return True
        
        return False
    
    @staticmethod
    def detect_conversation_end(messages: List[Dict]) -> bool:
        """Определить завершение разговора"""
        if not messages:
            return False
        
        last_message = messages[-1]
        last_time = last_message.get('created_at', datetime.utcnow())
        
        # Нет сообщений больше 6 часов
        if (datetime.utcnow() - last_time).seconds > 21600:  # 6 часов
            return True
        
        # Прощальные фразы
        farewell_phrases = ['пока', 'до свидания', 'увидимся', 'спокойной ночи', 'ладно, иду']
        text = last_message.get('text', '').lower()
        
        return any(phrase in text for phrase in farewell_phrases)


class SmartDelayCalculator:
    """Умный калькулятор задержек ответов"""
    
    @staticmethod
    def calculate_optimal_delay(
        message_urgency: str,
        user_emotion: str, 
        relationship_stage: str,
        current_hour: int,
        message_length: int
    ) -> int:
        """Расчет оптимальной задержки ответа"""
        
        base_delay = 15  # Базовая задержка в секундах
        
        # Корректировка по срочности
        urgency_multipliers = {
            'high': 0.3,     # Быстрый ответ на срочное
            'medium': 1.0,   # Обычная скорость
            'low': 1.8       # Можно ответить медленнее
        }
        
        # Корректировка по эмоции
        emotion_multipliers = {
            'negative': 0.5,   # Быстро отвечаем на негатив
            'excited': 0.7,    # Быстро на возбуждение
            'positive': 1.2,   # Чуть медленнее на позитив
            'neutral': 1.0     # Обычно
        }
        
        # Корректировка по стадии отношений
        stage_multipliers = {
            'initial': 2.0,      # В начале медленнее
            'warming_up': 1.5,   # Прогреваемся
            'friendly': 1.0,     # Дружеский темп
            'close': 0.8,        # Близко - быстрее
            'intimate': 0.6      # Интимно - очень быстро
        }
        
        # Корректировка по времени суток
        if 0 <= current_hour < 7:      # Ночь
            time_multiplier = 4.0
        elif 7 <= current_hour < 9:    # Раннее утро
            time_multiplier = 2.0
        elif 9 <= current_hour < 18:   # Рабочий день
            time_multiplier = 1.0
        elif 18 <= current_hour < 22:  # Вечер
            time_multiplier = 0.8
        else:                          # Поздний вечер
            time_multiplier = 1.5
        
        # Корректировка по длине сообщения
        length_addition = min(message_length * 0.1, 10)  # Максимум +10 секунд
        
        # Финальный расчет
        delay = base_delay * urgency_multipliers.get(message_urgency, 1.0)
        delay *= emotion_multipliers.get(user_emotion, 1.0)
        delay *= stage_multipliers.get(relationship_stage, 1.0)
        delay *= time_multiplier
        delay += length_addition
        
        # Добавляем случайность для естественности
        randomness = random.uniform(0.8, 1.2)
        delay *= randomness
        
        # Ограничиваем диапазон
        delay = max(5, min(int(delay), 120))  # От 5 секунд до 2 минут
        
        return delay


# Глобальные экземпляры
message_pattern_analyzer = MessagePatternAnalyzer()
smart_delay_calculator = SmartDelayCalculator()