"""
Продвинутые вспомогательные функции для улучшенного AI Companion
"""
import random
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger


class ProxyManager:
    """Менеджер прокси для ротации и проверки"""
    
    def __init__(self):
        self.proxies: List[Dict[str, str]] = []
        self.current_proxy_index = 0
        self.failed_proxies: set = set()
        
    def add_proxy(self, proxy_type: str, host: str, port: int, 
                  username: str = None, password: str = None):
        """Добавить прокси в список"""
        proxy = {
            'type': proxy_type,  # 'http', 'socks5', etc.
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'id': f"{host}:{port}"
        }
        self.proxies.append(proxy)
        logger.info(f"Добавлен прокси: {proxy['id']}")
    
    def get_current_proxy(self) -> Optional[Dict[str, str]]:
        """Получить текущий активный прокси"""
        if not self.proxies:
            return None
        
        # Пропускаем неработающие прокси
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_proxy_index]
            if proxy['id'] not in self.failed_proxies:
                return proxy
            
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            attempts += 1
        
        # Все прокси неработающие - очищаем список failed и начинаем заново
        logger.warning("Все прокси помечены как неработающие, сброс списка")
        self.failed_proxies.clear()
        return self.proxies[self.current_proxy_index] if self.proxies else None
    
    def rotate_proxy(self) -> Optional[Dict[str, str]]:
        """Переключиться на следующий прокси"""
        if not self.proxies:
            return None
        
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return self.get_current_proxy()
    
    def mark_proxy_failed(self, proxy_id: str):
        """Отметить прокси как неработающий"""
        self.failed_proxies.add(proxy_id)
        logger.warning(f"Прокси {proxy_id} помечен как неработающий")
    
    def get_telethon_proxy_config(self) -> Optional[Tuple]:
        """Получить конфигурацию прокси для Telethon"""
        proxy = self.get_current_proxy()
        if not proxy:
            return None
        
        # Формат для Telethon: (type, host, port, username, password)
        return (
            proxy['type'],
            proxy['host'], 
            proxy['port'],
            proxy.get('username'),
            proxy.get('password')
        )


class MessagePatternAnalyzer:
    """Анализатор паттернов сообщений пользователей"""
    
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
        if (datetime.utcnow() - last_time).hours > 6:
            return True
        
        # Прощальные фразы
        farewell_phrases = ['пока', 'до свидания', 'увидимся', 'спокойной ночи', 'ладно, иду']
        text = last_message.get('text', '').lower()
        
        return any(phrase in text for phrase in farewell_phrases)
    
    @staticmethod
    def get_user_activity_pattern(messages: List[Dict]) -> Dict[str, Any]:
        """Получить паттерн активности пользователя"""
        if not messages:
            return {'type': 'unknown', 'peak_hours': [], 'avg_response_time': 0}
        
        # Анализ времени активности
        hours = [msg.get('created_at', datetime.utcnow()).hour for msg in messages]
        hour_counts = {}
        for hour in hours:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        # Пиковые часы (топ 3)
        peak_hours = sorted(hour_counts.keys(), key=lambda h: hour_counts[h], reverse=True)[:3]
        
        # Тип активности
        if max(hour_counts.values()) > len(messages) * 0.4:
            activity_type = 'concentrated'  # Сконцентрированная активность
        elif len(hour_counts) > 12:
            activity_type = 'distributed'  # Распределенная активность
        else:
            activity_type = 'regular'  # Регулярная активность
        
        return {
            'type': activity_type,
            'peak_hours': peak_hours,
            'total_messages': len(messages),
            'unique_hours': len(hour_counts)
        }


class ResponseQualityAnalyzer:
    """Анализатор качества ответов ИИ"""
    
    @staticmethod
    def analyze_response_effectiveness(ai_message: str, user_response: str = None) -> Dict[str, Any]:
        """Анализ эффективности ответа ИИ"""
        analysis = {
            'length_score': ResponseQualityAnalyzer._score_length(ai_message),
            'question_score': ResponseQualityAnalyzer._score_questions(ai_message),
            'engagement_score': 0,
            'overall_score': 0
        }
        
        # Анализ реакции пользователя (если есть)
        if user_response:
            analysis['engagement_score'] = ResponseQualityAnalyzer._score_engagement(
                ai_message, user_response
            )
        
        # Общий балл
        scores = [analysis['length_score'], analysis['question_score'], analysis['engagement_score']]
        analysis['overall_score'] = sum(scores) / len([s for s in scores if s > 0])
        
        return analysis
    
    @staticmethod
    def _score_length(message: str) -> float:
        """Оценка длины сообщения (1-5 предложений = хорошо)"""
        sentences = message.count('.') + message.count('!') + message.count('?')
        if 1 <= sentences <= 3:
            return 1.0
        elif sentences == 4:
            return 0.8
        elif sentences >= 5:
            return 0.6
        else:
            return 0.4
    
    @staticmethod
    def _score_questions(message: str) -> float:
        """Оценка наличия вопросов"""
        question_count = message.count('?')
        if question_count == 1:
            return 1.0
        elif question_count == 2:
            return 0.8
        elif question_count >= 3:
            return 0.6
        else:
            return 0.3
    
    @staticmethod
    def _score_engagement(ai_message: str, user_response: str) -> float:
        """Оценка вовлеченности на основе ответа пользователя"""
        user_length = len(user_response.split())
        
        # Длинный ответ = хорошая вовлеченность
        if user_length > 20:
            return 1.0
        elif user_length > 10:
            return 0.8
        elif user_length > 5:
            return 0.6
        else:
            return 0.4


class SmartDelayCalculator:
    """Умный калькулятор задержек ответов"""
    
    @staticmethod
    def calculate_optimal_delay(
        message_urgency: str,
        user_emotion: str, 
        relationship_stage: str,
        current_hour: int,
        message_length: int,
        conversation_context: Dict[str, Any] = None
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
        
        # Корректировка по длине сообщения (симуляция времени чтения)
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


class ConversationFlowManager:
    """Менеджер потока разговора"""
    
    def __init__(self):
        self.conversation_stages = {
            'greeting': ['привет', 'hello', 'добро', 'здравствуй'],
            'question': ['?', 'что', 'как', 'где', 'когда', 'почему'],
            'statement': ['я', 'мне', 'у меня', 'думаю', 'считаю'],
            'farewell': ['пока', 'до свидания', 'увидимся', 'спокойной']
        }
    
    def classify_message_intent(self, message: str) -> str:
        """Классификация намерения сообщения"""
        message_lower = message.lower()
        
        for intent, keywords in self.conversation_stages.items():
            if any(keyword in message_lower for keyword in keywords):
                return intent
        
        return 'general'
    
    def suggest_response_type(self, user_intent: str, conversation_history: List[str]) -> str:
        """Предложение типа ответа в зависимости от намерения"""
        suggestions = {
            'greeting': 'reciprocal_greeting',
            'question': 'answer_and_ask',
            'statement': 'acknowledge_and_relate',
            'farewell': 'polite_farewell',
            'general': 'engaging_response'
        }
        
        return suggestions.get(user_intent, 'engaging_response')


# Глобальные экземпляры для использования в модулях
proxy_manager = ProxyManager()
conversation_flow_manager = ConversationFlowManager()