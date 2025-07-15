"""
Генератор ответов с использованием OpenAI API (Улучшенная версия)
"""
import json
import random
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from openai import OpenAI
from loguru import logger

from ..config.settings import settings, character_settings
from ..database.database import db_manager, MessageBatch
from ..utils.helpers import (
    extract_keywords, is_question, add_random_typo
)


class ConversationAnalyzer:
    """Анализатор контекста разговора"""
    
    @staticmethod
    def analyze_message_batch(batch: MessageBatch) -> Dict[str, Any]:
        """Анализ пакета сообщений"""
        if not batch.messages:
            return {'type': 'empty', 'urgency': 'low', 'emotion': 'neutral'}
        
        combined_text = batch.total_text.lower()
        message_count = len(batch.messages)
        
        # Определяем тип пакета
        message_type = 'single'
        if message_count > 1:
            if message_count <= 3:
                message_type = 'burst'  # короткая серия
            else:
                message_type = 'story'  # длинная история
        
        # Анализ эмоционального тона
        emotion = ConversationAnalyzer._detect_emotion_advanced(combined_text)
        
        # Определяем срочность ответа
        urgency = ConversationAnalyzer._calculate_urgency(batch, emotion)
        
        # Ключевые темы
        topics = ConversationAnalyzer._extract_topics(combined_text)
        
        # Есть ли вопросы
        has_questions = any(is_question(msg.text or "") for msg in batch.messages)
        
        return {
            'type': message_type,
            'emotion': emotion,
            'urgency': urgency,
            'topics': topics,
            'has_questions': has_questions,
            'message_count': message_count,
            'time_span_seconds': (batch.last_message_time - batch.first_message_time).total_seconds() if batch.last_message_time and batch.first_message_time else 0
        }
    
    @staticmethod
    def _detect_emotion_advanced(text: str) -> str:
        """Продвинутый анализ эмоций"""
        # Негативные эмоции
        negative_markers = [
            'плохо', 'грустно', 'устала', 'тяжело', 'проблема', 'болит', 
            'расстроена', 'злая', 'бесит', 'достало', 'ужасно', 'кошмар',
            'депрессия', 'паника', 'стресс', 'переживаю', 'волнуюсь'
        ]
        
        # Позитивные эмоции
        positive_markers = [
            'отлично', 'супер', 'классно', 'круто', 'рада', 'счастлива',
            'прекрасно', 'замечательно', 'восхитительно', 'обожаю', 'люблю',
            'в восторге', 'кайф', 'шикарно', 'потрясающе'
        ]
        
        # Возбужденные/энергичные
        excited_markers = [
            'вау', 'блин', 'офигеть', 'не могу поверить', 'представляешь',
            'срочно', 'быстрее', 'скорее', 'немедленно', 'прямо сейчас'
        ]
        
        negative_count = sum(1 for word in negative_markers if word in text)
        positive_count = sum(1 for word in positive_markers if word in text)
        excited_count = sum(1 for word in excited_markers if word in text)
        
        if excited_count > 0:
            return 'excited'
        elif negative_count > positive_count:
            return 'negative'
        elif positive_count > 0:
            return 'positive'
        else:
            return 'neutral'
    
    @staticmethod
    def _calculate_urgency(batch: MessageBatch, emotion: str) -> str:
        """Расчет срочности ответа"""
        message_count = len(batch.messages)
        
        # Множественные сообщения = выше срочность
        if message_count >= 4:
            return 'high'
        elif message_count >= 2:
            return 'medium'
        
        # Эмоциональные сообщения требуют быстрого ответа
        if emotion in ['negative', 'excited']:
            return 'high'
        elif emotion == 'positive':
            return 'medium'
        
        return 'low'
    
    @staticmethod
    def _extract_topics(text: str) -> List[str]:
        """Извлечение тем из текста"""
        topic_keywords = {
            'работа': ['работа', 'офис', 'коллега', 'проект', 'начальник', 'карьера', 'увольнение', 'зарплата'],
            'отношения': ['парень', 'девушка', 'свидание', 'любовь', 'расставание', 'семья', 'родители'],
            'здоровье': ['болею', 'врач', 'лечение', 'боль', 'таблетки', 'больница', 'самочувствие'],
            'досуг': ['кино', 'фильм', 'книга', 'игра', 'прогулка', 'ресторан', 'кафе', 'отдых'],
            'путешествия': ['поездка', 'отпуск', 'путешествие', 'самолет', 'море', 'горы', 'страна'],
            'учеба': ['университет', 'экзамен', 'учеба', 'диплом', 'курсы', 'преподаватель'],
            'спорт': ['зал', 'тренировка', 'бег', 'йога', 'спорт', 'фитнес', 'похудение']
        }
        
        found_topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                found_topics.append(topic)
        
        return found_topics


class ResponseGenerator:
    """Генератор ответов с ИИ (улучшенная версия)"""
    
    def __init__(self):
        try:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
            self.character = character_settings
            self.conversation_analyzer = ConversationAnalyzer()
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
    
    def _build_advanced_prompt(self, chat_context: Optional[Dict], message_batch: MessageBatch, 
                             analysis: Dict[str, Any], day: int) -> Tuple[str, str]:
        """Построение продвинутого промпта для пакета сообщений"""
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
        
        # Анализ пакета сообщений
        message_analysis = f"""
АНАЛИЗ ЕЁ СООБЩЕНИЙ:
- Тип пакета: {analysis['type']} ({analysis['message_count']} сообщений)
- Эмоциональный тон: {analysis['emotion']}
- Срочность ответа: {analysis['urgency']}
- Есть вопросы: {'Да' if analysis['has_questions'] else 'Нет'}
- Темы: {', '.join(analysis['topics']) if analysis['topics'] else 'общие'}
- Временной промежуток: {analysis['time_span_seconds']:.0f} секунд
"""
        
        # Специальные инструкции в зависимости от анализа
        response_strategy = self._get_response_strategy(analysis)
        
        system_prompt = base_prompt + character_info + context_info + scenario_info + message_analysis + response_strategy
        
        # Пользовательский промпт
        user_prompt = self._build_user_prompt(message_batch, analysis)
        
        return system_prompt, user_prompt
    
    def _get_response_strategy(self, analysis: Dict[str, Any]) -> str:
        """Получить стратегию ответа в зависимости от анализа"""
        strategy = "\nСТРАТЕГИЯ ОТВЕТА:\n"
        
        # Стратегия по типу сообщений
        if analysis['type'] == 'burst':
            strategy += "- Это серия быстрых сообщений - отвечай естественно на всю последовательность\n"
        elif analysis['type'] == 'story':
            strategy += "- Это длинная история - покажи что внимательно слушал, задай уточняющий вопрос\n"
        
        # Стратегия по эмоциям
        if analysis['emotion'] == 'negative':
            strategy += "- Она расстроена - будь поддерживающим и сочувствующим\n"
        elif analysis['emotion'] == 'excited':
            strategy += "- Она возбуждена/взволнована - разделяй её энергию\n"
        elif analysis['emotion'] == 'positive':
            strategy += "- Она в хорошем настроении - поддерживай позитив\n"
        
        # Стратегия по срочности
        if analysis['urgency'] == 'high':
            strategy += "- Высокая срочность - отвечай быстро и по делу\n"
        elif analysis['urgency'] == 'medium':
            strategy += "- Средняя срочность - можешь развить тему\n"
        
        # Стратегия по вопросам
        if analysis['has_questions']:
            strategy += "- Есть вопросы - обязательно ответь на них\n"
        
        return strategy
    
    def _build_user_prompt(self, message_batch: MessageBatch, analysis: Dict[str, Any]) -> str:
        """Построение пользовательского промпта"""
        if not message_batch.messages:
            return "Нет новых сообщений для обработки."
        
        # Получаем историю разговора
        chat_id = message_batch.messages[0].chat_id
        chat_history = db_manager.get_recent_conversation_context(chat_id, limit=15)
        
        # Формируем промпт в зависимости от типа сообщений
        if len(message_batch.messages) == 1:
            # Одно сообщение
            message = message_batch.messages[0]
            user_prompt = f"""
ИСТОРИЯ ДИАЛОГА:
{chat_history}

НОВОЕ СООБЩЕНИЕ ОТ НЕЁ:
[{message.created_at.strftime('%H:%M:%S')}] {message.text}

ИНСТРУКЦИЯ:
Ответь естественно на её сообщение, учитывая эмоциональный тон ({analysis['emotion']}) и контекст.
{"Обязательно ответь на её вопрос." if analysis['has_questions'] else ""}
Максимум 2-3 предложения!
"""
        else:
            # Множественные сообщения
            messages_text = message_batch.total_text
            time_span = analysis['time_span_seconds']
            
            user_prompt = f"""
ИСТОРИЯ ДИАЛОГА:
{chat_history}

ПАКЕТ НОВЫХ СООБЩЕНИЙ ОТ НЕЁ (за {time_span:.0f} секунд):
{messages_text}

ИНСТРУКЦИЯ:
Она отправила {len(message_batch.messages)} сообщений подряд. Это показывает что тема важна для неё.
Ответь на ВСЮ последовательность сообщений естественно, как живой человек.
{"Обязательно ответь на все её вопросы." if analysis['has_questions'] else ""}
Эмоциональный тон: {analysis['emotion']}
Максимум 2-3 предложения, но покрой все важные моменты!
"""
        
        return user_prompt
    
    async def generate_response_for_batch(self, chat_id: int, message_batch: MessageBatch) -> Optional[str]:
        """Генерация ответа на пакет сообщений"""
        try:
            if not message_batch.messages:
                logger.warning("Пустой пакет сообщений")
                return None
            
            # Анализируем пакет сообщений
            analysis = self.conversation_analyzer.analyze_message_batch(message_batch)
            
            logger.info(f"Обрабатываем пакет: {message_batch.get_context_summary()}")
            logger.debug(f"Анализ пакета: {analysis}")
            
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
            
            # Строим продвинутый промпт
            system_prompt, user_prompt = self._build_advanced_prompt(
                context_dict, message_batch, analysis, day
            )
            
            # Обновляем контекст чата
            self._update_chat_context_from_batch(chat_id, message_batch, analysis)
            
            # Формируем запрос к OpenAI
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
            
            logger.info(f"Сгенерирован ответ на пакет: {final_text[:50]}...")
            return final_text
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа на пакет: {e}")
            return self._get_fallback_response_for_batch(message_batch, analysis)
    
    # LEGACY метод для совместимости
    async def generate_response(self, chat_id: int, incoming_message: str) -> Optional[str]:
        """Генерация ответа на одиночное сообщение (устаревший метод)"""
        logger.warning("Используется устаревший метод generate_response. Рекомендуется использовать generate_response_for_batch")
        
        # Создаем фиктивный пакет из одного сообщения
        from ..database.models import Message
        fake_message = Message(
            chat_id=chat_id,
            text=incoming_message,
            is_from_ai=False,
            created_at=datetime.utcnow()
        )
        
        batch = MessageBatch([fake_message])
        return await self.generate_response_for_batch(chat_id, batch)
    
    def _update_chat_context_from_batch(self, chat_id: int, message_batch: MessageBatch, analysis: Dict[str, Any]):
        """Обновление контекста чата на основе анализа пакета"""
        try:
            # Извлекаем ключевые слова из всех сообщений
            all_keywords = []
            for message in message_batch.messages:
                if message.text:
                    all_keywords.extend(extract_keywords(message.text))
            
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
                if any(word in all_keywords for word in interest_words):
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
    
    def _get_fallback_response_for_batch(self, message_batch: MessageBatch, analysis: Dict[str, Any]) -> str:
        """Резервные ответы при ошибке API для пакетов"""
        emotion = analysis.get('emotion', 'neutral')
        message_count = len(message_batch.messages)
        
        if emotion == "negative":
            fallback_responses = [
                "Понимаю тебя( Хочешь поговорить об этом подробнее?",
                "Эх, бывает такое... Что именно расстроило?",
                "Держись! Расскажи что случилось?",
            ]
        elif emotion == "positive":
            fallback_responses = [
                "Круто! Расскажи подробнее)",
                "Вау, здорово! А что именно так порадовало?",
                "Отлично! Я за тебя рад)",
            ]
        elif emotion == "excited":
            fallback_responses = [
                "Ого! Чувствую твою энергию) Что такое?",
                "Вау! Рассказывай быстрее!",
                "Интригуешь! Жду продолжения)",
            ]
        else:
            if analysis.get('has_questions'):
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
        
        response = random.choice(fallback_responses)
        
        # Добавляем комментарий если много сообщений
        if message_count > 2:
            response += f" (Вижу ты написала {message_count} сообщений - тема важная!)"
        
        return response
    
    def should_respond(self, chat_id: int, message_batch: MessageBatch) -> bool:
        """Всегда отвечаем на пакеты сообщений"""
        return True
    
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