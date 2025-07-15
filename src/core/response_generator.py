"""
Генератор ответов с использованием OpenAI API
"""
import json
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from openai import OpenAI
from loguru import logger

from ..config.settings import settings, character_settings
from ..database.database import db_manager
from ..utils.helpers import (
    extract_keywords, is_question, format_chat_history_for_ai,
    add_random_typo
)


class ResponseGenerator:
    """Генератор ответов с ИИ"""
    
    def __init__(self):
        try:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
            self.character = character_settings
        except Exception as e:
            logger.error(f"Ошибка инициализации OpenAI клиента: {e}")
            raise
    
    def _get_relationship_stage_days(self, chat_context) -> int:
        """Определить количество дней общения"""
        if not chat_context:
            return 1
        
        days_diff = (datetime.utcnow() - chat_context.updated_at).days
        return max(1, chat_context.messages_count // 10)  # примерно 10 сообщений = 1 день
    
    def _get_scenario_for_day(self, day: int) -> Optional[str]:
        """Получить сценарий для конкретного дня"""
        scenarios = self.character.relationship_scenarios
        
        if day == 2 and random.random() < 0.3:  # 30% шанс в день 2
            return "work_stress"
        elif day == 3 and random.random() < 0.4:  # 40% шанс в день 3  
            return "family_call"
        elif day >= 5 and random.random() < 0.2:  # 20% шанс после 5 дня
            return "weekend_plans"
        elif day >= 7 and random.random() < 0.15:  # 15% шанс после недели
            return "meeting_suggestion"
        
        return None
    
    def _build_adaptive_prompt(self, chat_context: Optional[Dict], incoming_message: str, day: int) -> str:
        """Построение адаптивного промпта"""
        base_prompt = self.character.system_prompt
        
        # Информация о персонаже
        character_info = f"""
ТВОЯ БИОГРАФИЯ:
{self.character.background_story}

ТВОИ ИНТЕРЕСЫ: {', '.join(self.character.interests)}
ТВОЙ ХАРАКТЕР: {', '.join(self.character.personality_traits)}

ИСТОРИИ ИЗ ЖИЗНИ (используй по ситуации):
"""
        for story_key, story_text in self.character.life_stories.items():
            character_info += f"- {story_text}\n"
        
        # Контекст диалога
        context_info = ""
        if chat_context:
            detected_interests = json.loads(chat_context.get('detected_interests', '[]'))
            context_info = f"""
КОНТЕКСТ ДИАЛОГА:
- День общения: {day}
- Стадия отношений: {chat_context.get('relationship_stage', 'начальная')}
- Всего сообщений: {chat_context.get('messages_count', 0)}
- Её интересы: {', '.join(detected_interests) if detected_interests else 'изучаешь'}
"""
        
        # Сценарий дня (если есть)
        scenario = self._get_scenario_for_day(day)
        scenario_info = ""
        if scenario:
            scenario_info = f"""
СЦЕНАРИЙ ДНЯ: {scenario}
- Если work_stress: расскажи о сложностях на работе, спроси совета
- Если family_call: упомяни звонок от мамы/семьи
- Если weekend_plans: обсуди планы на выходные, намекни на встречу
- Если meeting_suggestion: аккуратно предложи встретиться
"""
        
        # Анализ сообщения девушки
        message_analysis = f"""
АНАЛИЗ ЕЁ СООБЩЕНИЯ: "{incoming_message}"
- Это вопрос: {'Да' if is_question(incoming_message) else 'Нет'}
- Ключевые слова: {', '.join(extract_keywords(incoming_message))}
- Эмоциональный тон: {self._detect_emotion(incoming_message)}
"""
        
        return base_prompt + character_info + context_info + scenario_info + message_analysis
    
    def _detect_emotion(self, message: str) -> str:
        """Определить эмоциональный тон сообщения"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['плохо', 'грустно', 'устала', 'тяжело', 'проблема']):
            return "негативный"
        elif any(word in message_lower for word in ['отлично', 'супер', 'классно', 'круто', 'рада']):
            return "позитивный"
        elif any(word in message_lower for word in ['скучно', 'норм', 'обычно', 'ничего']):
            return "нейтральный"
        else:
            return "нейтральный"
    
    def _get_chat_history(self, chat_id: int) -> str:
        """Получить историю чата для контекста"""
        messages = db_manager.get_chat_messages(chat_id, limit=15)  # больше контекста
        
        formatted_messages = []
        for msg in messages[-10:]:  # последние 10 для экономии токенов
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
            
            # Определяем день общения
            day = self._get_relationship_stage_days(chat_context)
            
            # Строим адаптивный промпт
            system_prompt = self._build_adaptive_prompt(context_dict, incoming_message, day)
            chat_history = self._get_chat_history(chat_id)
            
            # Анализируем входящее сообщение
            keywords = extract_keywords(incoming_message)
            emotion = self._detect_emotion(incoming_message)
            
            # Обновляем контекст чата
            self._update_chat_context(chat_id, incoming_message, keywords, emotion)
            
            # Формируем запрос к OpenAI
            user_prompt = f"""
ИСТОРИЯ ДИАЛОГА:
{chat_history}

НОВОЕ СООБЩЕНИЕ ОТ НЕЁ: "{incoming_message}"

ИНСТРУКЦИЯ:
Ответь естественно, учитывая день общения ({day}) и эмоциональный тон её сообщения ({emotion}).
Используй сценарий дня если подходит момент.
Обязательно задай вопрос или проявий интерес к ней.
Максимум 2 предложения!
"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
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
    
    def _update_chat_context(self, chat_id: int, message: str, keywords: List[str], emotion: str):
        """Обновление контекста чата с детальной аналитикой"""
        try:
            # Расширенный анализ интересов
            interest_keywords = {
                'спорт': ['спорт', 'футбол', 'бег', 'зал', 'тренировка', 'фитнес', 'йога', 'плавание'],
                'путешествия': ['путешествие', 'отпуск', 'море', 'горы', 'страна', 'город', 'поездка', 'отдых'],
                'кино': ['фильм', 'кино', 'сериал', 'актер', 'режиссер', 'нетфликс'],
                'музыка': ['музыка', 'песня', 'концерт', 'группа', 'исполнитель', 'альбом'],
                'работа': ['работа', 'офис', 'коллега', 'проект', 'карьера', 'начальник', 'учеба'],
                'еда': ['кафе', 'ресторан', 'готовить', 'рецепт', 'вкусно', 'еда', 'кухня'],
                'животные': ['кот', 'собака', 'животные', 'питомец', 'котик', 'пес'],
                'книги': ['книга', 'читать', 'автор', 'роман', 'литература'],
                'хобби': ['рисование', 'фотография', 'творчество', 'рукоделие', 'вязание']
            }
            
            detected_interests = []
            for interest, interest_words in interest_keywords.items():
                if any(word in keywords for word in interest_words):
                    detected_interests.append(interest)
            
            # Определяем стадию отношений
            context = db_manager.get_chat_context(chat_id)
            current_stage = context.relationship_stage if context else 'initial'
            message_count = context.messages_count if context else 0
            
            # Более точная стадия отношений
            if message_count > 50:
                new_stage = 'intimate'
            elif message_count > 30:
                new_stage = 'close'
            elif message_count > 15:
                new_stage = 'friendly'
            elif message_count > 5:
                new_stage = 'warming_up'
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
                logger.info(f"Стадия отношений изменена: {current_stage} → {new_stage}")
            
            if update_data:
                db_manager.update_chat_context(chat_id, **update_data)
                
        except Exception as e:
            logger.error(f"Ошибка обновления контекста: {e}")
    
    def _get_fallback_response(self, incoming_message: str) -> str:
        """Резервные ответы при ошибке API"""
        emotion = self._detect_emotion(incoming_message)
        
        if emotion == "негативный":
            fallback_responses = [
                "Понимаю тебя( Хочешь поговорить об этом?",
                "Эх, бывает такое... Что случилось?",
                "Держись! А что именно расстроило?",
            ]
        elif emotion == "позитивный":
            fallback_responses = [
                "Круто! Расскажи подробнее)",
                "Вау, здорово! А что именно так порадовало?",
                "Отлично! Я за тебя рад)",
            ]
        else:
            if is_question(incoming_message):
                fallback_responses = [
                    "Хороший вопрос) Думаю... А ты как считаешь?",
                    "Сложно сказать, но скорее да. А у тебя какое мнение?",
                    "Интересно спрашиваешь) По-моему..."
                ]
            else:
                fallback_responses = [
                    "Интересно! А ты часто этим занимаешься?",
                    "Согласен) А как тебе это нравится?",
                    "Понятно) А что думаешь делать дальше?",
                ]
        
        return random.choice(fallback_responses)
    
    def should_respond(self, chat_id: int, message: str) -> bool:
        """ВСЕГДА отвечаем - это главное изменение!"""
        return True  # Убираем 70% логику - всегда отвечаем!
    
    def get_character_info(self) -> Dict[str, Any]:
        """Получить информацию о персонаже"""
        return {
            'name': self.character.name,
            'age': self.character.age,
            'occupation': self.character.occupation,
            'location': self.character.location,
            'interests': self.character.interests,
            'personality': self.character.personality_traits,
            'background': self.character.background_story
        }