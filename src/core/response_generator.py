"""
Генератор ответов с использованием OpenAI API
"""
import json
import random
from typing import List, Dict, Any, Optional
from openai import OpenAI
from loguru import logger

from ..config.settings import settings, character_settings
from ..database.database import db_manager
from ..utils.helpers import (
    extract_keywords, is_question, format_chat_history_for_ai,
    should_respond_to_message, add_random_typo
)


class ResponseGenerator:
    """Генератор ответов с ИИ"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        self.character = character_settings
        
    def _build_system_prompt(self, chat_context: Optional[Dict] = None) -> str:
        """Построение системного промпта с учетом контекста"""
        base_prompt = self.character.system_prompt
        
        # Добавляем информацию о персонаже
        character_info = f"""
        
Информация о тебе:
- Имя: {self.character.name}
- Возраст: {self.character.age}
- Профессия: {self.character.occupation}
- Город: {self.character.location}
- Интересы: {', '.join(self.character.interests)}
- Характер: {', '.join(self.character.personality_traits)}

Правила общения:
1. Отвечай кратко (1-2 предложения)
2. Используй естественную речь с сокращениями
3. Проявляй интерес к собеседнице
4. Задавай встречные вопросы
5. Избегай шаблонных фраз
6. Будь дружелюбным и слегка флиртующим
        """
        
        # Добавляем контекст диалога если есть
        if chat_context:
            context_info = f"""
            
Контекст диалога:
- Стадия отношений: {chat_context.get('relationship_stage', 'начальная')}
- Количество сообщений: {chat_context.get('messages_count', 0)}
- Интересы собеседницы: {chat_context.get('detected_interests', 'не определены')}
            """
            character_info += context_info
        
        return base_prompt + character_info
    
    def _get_chat_history(self, chat_id: int) -> str:
        """Получить историю чата для контекста"""
        messages = db_manager.get_chat_messages(chat_id, limit=10)
        
        formatted_messages = []
        for msg in messages:
            role = "Ты" if msg.is_from_ai else "Она"
            if msg.text:
                formatted_messages.append(f"{role}: {msg.text}")
        
        return "\n".join(formatted_messages) if formatted_messages else "Начало диалога"
    
    async def generate_response(self, chat_id: int, incoming_message: str) -> Optional[str]:
        """Генерация ответа на сообщение"""
        try:
            # Получаем контекст чата
            chat_context = db_manager.get_chat_context(chat_id)
            context_dict = {}
            
            if chat_context:
                context_dict = {
                    'relationship_stage': chat_context.relationship_stage,
                    'messages_count': chat_context.messages_count,
                    'detected_interests': chat_context.detected_interests
                }
            
            # Строим промпт
            system_prompt = self._build_system_prompt(context_dict)
            chat_history = self._get_chat_history(chat_id)
            
            # Анализируем входящее сообщение
            keywords = extract_keywords(incoming_message)
            is_quest = is_question(incoming_message)
            
            # Обновляем контекст чата
            self._update_chat_context(chat_id, incoming_message, keywords)
            
            # Формируем запрос к OpenAI
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""
Последние сообщения диалога:
{chat_history}

Новое сообщение от девушки: "{incoming_message}"

Ответь естественно, как мужчина, который флиртует и проявляет интерес к собеседнице.
{'Девушка задала вопрос, обязательно ответь на него.' if is_quest else ''}
"""}
            ]
            
            # Отправляем запрос к OpenAI
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature
            )
            
            generated_text = response.choices[0].message.content.strip()
            
            # Добавляем случайные опечатки для реалистичности
            final_text = add_random_typo(generated_text)
            
            logger.info(f"Сгенерирован ответ: {final_text[:50]}...")
            return final_text
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return self._get_fallback_response(incoming_message)
    
    def _update_chat_context(self, chat_id: int, message: str, keywords: List[str]):
        """Обновление контекста чата"""
        try:
            # Анализируем интересы
            interest_keywords = {
                'спорт': ['спорт', 'футбол', 'бег', 'зал', 'тренировка', 'фитнес'],
                'путешествия': ['путешествие', 'отпуск', 'море', 'горы', 'страна', 'город'],
                'кино': ['фильм', 'кино', 'сериал', 'актер', 'режиссер'],
                'музыка': ['музыка', 'песня', 'концерт', 'группа', 'исполнитель'],
                'работа': ['работа', 'офис', 'коллега', 'проект', 'карьера', 'начальник'],
                'еда': ['кафе', 'ресторан', 'готовить', 'рецепт', 'вкусно', 'еда']
            }
            
            detected_interests = []
            for interest, interest_words in interest_keywords.items():
                if any(word in keywords for word in interest_words):
                    detected_interests.append(interest)
            
            # Определяем стадию отношений
            context = db_manager.get_chat_context(chat_id)
            current_stage = context.relationship_stage if context else 'initial'
            
            message_count = context.messages_count if context else 0
            
            if message_count > 20:
                new_stage = 'close'
            elif message_count > 5:
                new_stage = 'friendly'
            else:
                new_stage = 'initial'
            
            # Обновляем контекст
            update_data = {}
            if detected_interests:
                existing_interests = json.loads(context.detected_interests) if context and context.detected_interests else []
                all_interests = list(set(existing_interests + detected_interests))
                update_data['detected_interests'] = json.dumps(all_interests)
            
            if new_stage != current_stage:
                update_data['relationship_stage'] = new_stage
            
            if update_data:
                db_manager.update_chat_context(chat_id, **update_data)
                
        except Exception as e:
            logger.error(f"Ошибка обновления контекста: {e}")
    
    def _get_fallback_response(self, incoming_message: str) -> str:
        """Резервные ответы при ошибке API"""
        fallback_responses = [
            "Интересно, расскажи подробнее)",
            "А я как раз думал о том же!",
            "Согласен, это правда важно",
            "Хм, а как ты к этому относишься?",
            "Точно! А у тебя есть опыт в этом?",
            "Понимаю тебя. А что думаешь делать дальше?",
            "Это здорово! Мне тоже нравится такое",
            "А я вот недавно тоже с таким сталкивался"
        ]
        
        # Специальные ответы на вопросы
        if is_question(incoming_message):
            question_responses = [
                "Хороший вопрос) Мне кажется...",
                "Думаю, что да. А ты как считаешь?",
                "Сложно сказать, но по опыту...",
                "А ты сама как думаешь об этом?",
                "Интересно спрашиваешь) По-моему..."
            ]
            return random.choice(question_responses)
        
        return random.choice(fallback_responses)
    
    def should_respond(self, chat_id: int, message: str) -> bool:
        """Определить, нужно ли отвечать на сообщение"""
        try:
            # Получаем последнее сообщение ИИ
            messages = db_manager.get_chat_messages(chat_id, limit=5)
            last_ai_message = None
            
            for msg in reversed(messages):
                if msg.is_from_ai:
                    last_ai_message = msg
                    break
            
            last_ai_time = last_ai_message.created_at if last_ai_message else None
            
            return should_respond_to_message(message, last_ai_time)
            
        except Exception as e:
            logger.error(f"Ошибка проверки необходимости ответа: {e}")
            return True  # По умолчанию отвечаем
    
    def get_character_info(self) -> Dict[str, Any]:
        """Получить информацию о персонаже"""
        return {
            'name': self.character.name,
            'age': self.character.age,
            'occupation': self.character.occupation,
            'location': self.character.location,
            'interests': self.character.interests,
            'personality': self.character.personality_traits
        }