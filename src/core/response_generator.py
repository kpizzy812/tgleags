"""
Генератор реалистичных ответов на основе анализа успешных диалогов знакомств
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
    """Анализатор контекста разговора для реалистичных ответов"""
    
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
        
        # Анализ намерений (для знакомств)
        intent = ConversationAnalyzer._detect_dating_intent(combined_text)
        
        return {
            'type': message_type,
            'emotion': emotion,
            'urgency': urgency,
            'topics': topics,
            'has_questions': has_questions,
            'intent': intent,
            'message_count': message_count,
            'time_span_seconds': (batch.last_message_time - batch.first_message_time).total_seconds() if batch.last_message_time and batch.first_message_time else 0
        }
    
    @staticmethod
    def _detect_emotion_advanced(text: str) -> str:
        """Продвинутый анализ эмоций"""
        # Позитивные эмоции
        positive_markers = [
            'отлично', 'супер', 'классно', 'круто', 'рада', 'счастлива', 'хорошо',
            'прекрасно', 'замечательно', 'здорово', 'нравится', 'интересно'
        ]
        
        # Нейтрально-рабочие
        work_markers = [
            'работаю', 'рабочее', 'работе', 'делаю', 'занимаюсь', 'трудишься', 'работой'
        ]
        
        # Любопытство/интерес
        curious_markers = [
            'интересно', 'как', 'что', 'где', 'расскажи', 'хочется', 'думала'
        ]
        
        # Флирт/игривость
        flirty_markers = [
            'говорящее', 'звучит здорово', 'давай', 'можем', 'хочется'
        ]
        
        positive_count = sum(1 for word in positive_markers if word in text)
        work_count = sum(1 for word in work_markers if word in text)
        curious_count = sum(1 for word in curious_markers if word in text)
        flirty_count = sum(1 for word in flirty_markers if word in text)
        
        if flirty_count > 0:
            return 'flirty'
        elif curious_count > 1:
            return 'curious'
        elif work_count > 0:
            return 'focused'
        elif positive_count > 0:
            return 'positive'
        else:
            return 'neutral'
    
    @staticmethod
    def _detect_dating_intent(text: str) -> str:
        """Определение намерений в контексте знакомств"""
        
        # Знакомство/начальная фаза
        intro_markers = ['привет', 'как дела', 'настроение', 'чем занимаешься']
        
        # Интерес к работе/жизни
        work_interest = ['кем работаешь', 'чем занимаешься', 'трудишься', 'как давно']
        
        # Личный интерес
        personal_interest = ['свободное время', 'хочется', 'нравится', 'думаешь']
        
        # Предложение встречи/работы
        meeting_intent = ['созвониться', 'встретиться', 'помощница', 'работа', 'давай']
        
        if any(marker in text for marker in meeting_intent):
            return 'meeting_proposal'
        elif any(marker in text for marker in personal_interest):
            return 'personal_interest'
        elif any(marker in text for marker in work_interest):
            return 'work_interest'
        elif any(marker in text for marker in intro_markers):
            return 'introduction'
        else:
            return 'general'
    
    @staticmethod
    def _calculate_urgency(batch: MessageBatch, emotion: str) -> str:
        """Расчет срочности ответа"""
        message_count = len(batch.messages)
        
        # Множественные сообщения = выше срочность
        if message_count >= 3:
            return 'high'
        elif message_count >= 2:
            return 'medium'
        
        # Эмоциональные сообщения требуют быстрого ответа
        if emotion in ['flirty', 'curious']:
            return 'high'
        elif emotion == 'positive':
            return 'medium'
        
        return 'low'
    
    @staticmethod
    def _extract_topics(text: str) -> List[str]:
        """Извлечение тем из текста"""
        topic_keywords = {
            'работа': ['работа', 'работаю', 'трудишься', 'администратор', 'магазин', 'трейдинг', 'акции', 'криптовалюта'],
            'хобби': ['свободное время', 'занимаешься', 'интересы', 'хобби'],
            'знакомство': ['привет', 'настроение', 'как дела', 'познакомиться'],
            'личное': ['нравится', 'хочется', 'думаешь', 'чувствуешь'],
            'встреча': ['созвониться', 'встретиться', 'свидание', 'увидимся'],
            'техника': ['пк', 'компьютер', 'новый', 'имеет значение']
        }
        
        found_topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                found_topics.append(topic)
        
        return found_topics


class ResponseGenerator:
    """Генератор реалистичных ответов для знакомств"""
    
    def __init__(self):
        try:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
            self.character = character_settings
            self.conversation_analyzer = ConversationAnalyzer()
        except Exception as e:
            logger.error(f"Ошибка инициализации OpenAI клиента: {e}")
            raise
    
    def _get_relationship_stage_days(self, chat_context) -> int:
        """Определить стадию отношений по дням"""
        if not chat_context:
            return 1
        
        # Примерно 5-8 сообщений = 1 день общения
        days = max(1, chat_context.messages_count // 6)
        return min(days, 14)  # Максимум 2 недели для этой системы
    
    def _build_realistic_prompt(self, chat_context: Optional[Dict], message_batch: MessageBatch, 
                              analysis: Dict[str, Any], day: int) -> Tuple[str, str]:
        """Построение промпта для максимально реалистичных диалогов"""
        
        # СИСТЕМНЫЙ ПРОМПТ - максимально реалистичный
        system_prompt = f"""Ты {self.character.name}, {self.character.age}-летний {self.character.occupation.lower()} из {self.character.location}. Познакомился с девушкой на сайте знакомств.

ТВОЯ ГЛАВНАЯ ЦЕЛЬ: Построить естественные отношения и пригласить на свидание.

КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:
1. ВСЕГДА отвечай КРАТКО - максимум 1-2 предложения
2. ВСЕГДА задавай встречный вопрос (как в примере: "А ты кем?", "А как у тебя?")
3. Показывай ЖИВОЙ интерес к ней - комментируй её ответы
4. Пиши как живой человек - с сокращениями, без формальности
5. Постепенно углубляй темы: работа → интересы → личное → встреча

ТВОЯ ЛИЧНОСТЬ:
- {self.character.background_story}
- Интересы: {', '.join(self.character.interests)}
- Характер: {', '.join(self.character.personality_traits)}

ПРИМЕРЫ ИДЕАЛЬНЫХ ОТВЕТОВ:
• На "Как настроение?" → "Отличное. Как твое?"
• На работе → "Администратор в магазине. Ты кем?"
• На интерес → "Звучит здорово.) Если бы не нравилось не работала бы. Как давно занимаешься?"
• Живые реакции → "Настроение говорящее у тебя.)"

СТРАТЕГИЯ ПО ДНЯМ:
День 1-2: Знакомство, работа, общие темы
День 3-4: Интересы, хобби, более личные вопросы  
День 5-7: Свободное время, планы, намеки на встречу
День 7+: Предложение созвониться/встретиться

ТЕКУЩИЙ ДЕНЬ: {day}
"""

        # Анализ контекста для персонализации
        context_info = ""
        if chat_context:
            try:
                detected_interests_raw = chat_context.get('detected_interests', '[]')
                logger.debug(f"detected_interests_raw: {detected_interests_raw}, type: {type(detected_interests_raw)}")

                if detected_interests_raw and detected_interests_raw not in [None, 'null', '']:
                    detected_interests = json.loads(detected_interests_raw)
                else:
                    detected_interests = []
        
                if detected_interests:
                    context_info = f"\nЧТО ЗНАЕШЬ О НЕЙ: {', '.join(detected_interests)}"
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                logger.error(f"Ошибка парсинга detected_interests: {e}")
                detected_interests = []
        
        # Специальные инструкции на основе анализа
        special_instructions = self._get_response_strategy_realistic(analysis, day)
        
        full_system_prompt = system_prompt + context_info + special_instructions
        
        # ПОЛЬЗОВАТЕЛЬСКИЙ ПРОМПТ - контекст диалога
        user_prompt = self._build_user_prompt_realistic(message_batch, analysis, day)
        
        return full_system_prompt, user_prompt
    
    def _get_response_strategy_realistic(self, analysis: Dict[str, Any], day: int) -> str:
        """Реалистичная стратегия ответа"""
        strategy = "\n\nСПЕЦИАЛЬНЫЕ ИНСТРУКЦИИ:\n"
        
        # По эмоции
        emotion = analysis.get('emotion', 'neutral')
        if emotion == 'flirty':
            strategy += "- Она флиртует - отвечай игриво, но не навязчиво\n"
        elif emotion == 'curious':
            strategy += "- Она любопытная - удовлетвори интерес и задай встречный вопрос\n"
        elif emotion == 'focused':
            strategy += "- Она сосредоточена на работе - покажи понимание и интерес\n"
        
        # По намерениям
        intent = analysis.get('intent', 'general')
        if intent == 'work_interest':
            strategy += "- Отвечай на вопросы о работе честно + задавай аналогичный вопрос о ней\n"
        elif intent == 'personal_interest':
            strategy += "- Она интересуется твоей личной жизнью - будь открытым\n"
        elif intent == 'meeting_proposal':
            strategy += "- Возможно намек на встречу - реагируй заинтересованно\n"
        
        # По дню знакомства
        if day <= 2:
            strategy += "- Начало знакомства - будь дружелюбным, задавай базовые вопросы\n"
        elif day <= 4:
            strategy += "- Углубляй знакомство - более личные темы и интересы\n"
        elif day >= 5:
            strategy += "- Время предлагать встречу - спрашивай про свободное время\n"
        
        # По вопросам
        if analysis.get('has_questions'):
            strategy += "- ОБЯЗАТЕЛЬНО ответь на её вопрос + задай свой\n"
        
        strategy += "\nПОМНИ: Максимум 2 предложения! Всегда задавай встречный вопрос!"
        
        return strategy
    
    def _build_user_prompt_realistic(self, message_batch: MessageBatch, analysis: Dict[str, Any], day: int) -> str:
        """Реалистичный пользовательский промпт"""
        
        # Получаем недавнюю историю диалога
        if message_batch.messages:
            chat_id = message_batch.messages[0].chat_id
            chat_history = db_manager.get_recent_conversation_context(chat_id, limit=10)
        else:
            chat_history = "Начало диалога"
        
        # Анализируем что она написала
        if len(message_batch.messages) == 1:
            message = message_batch.messages[0]
            user_prompt = f"""НЕДАВНЯЯ ИСТОРИЯ:
{chat_history}

ОНА ТОЛЬКО ЧТО НАПИСАЛА:
{message.text}

АНАЛИЗ: {analysis['emotion']} настроение, намерение: {analysis['intent']}
{f"ЕСТЬ ВОПРОС - обязательно ответь!" if analysis['has_questions'] else ""}

ОТВЕТЬ ЕСТЕСТВЕННО (1-2 предложения + встречный вопрос):"""
        
        else:
            # Множественные сообщения
            messages_text = message_batch.total_text
            user_prompt = f"""НЕДАВНЯЯ ИСТОРИЯ:
{chat_history}

ОНА НАПИСАЛА НЕСКОЛЬКО СООБЩЕНИЙ:
{messages_text}

АНАЛИЗ: {analysis['emotion']} настроение, {len(message_batch.messages)} сообщений, намерение: {analysis['intent']}

ОТВЕТЬ НА ВСЕ (1-2 предложения + встречный вопрос):"""
        
        return user_prompt
    
    async def generate_response_for_batch(self, chat_id: int, message_batch: MessageBatch) -> Optional[str]:
        """Генерация реалистичного ответа на пакет сообщений"""
        try:
            if not message_batch.messages:
                logger.warning("Пустой пакет сообщений")
                return None
            
            # Анализируем пакет
            analysis = self.conversation_analyzer.analyze_message_batch(message_batch)
            
            logger.info(f"📥 Анализ: {analysis['emotion']} настроение, {analysis['intent']} намерение")
            
            # Получаем контекст чата
            chat_context = db_manager.get_chat_context(chat_id)
            context_dict = {}
            
            if chat_context:
                logger.debug(f"Chat context detected_interests: {chat_context.detected_interests}")
                logger.debug(f"Chat context type: {type(chat_context.detected_interests)}")
    
                context_dict = {
                    'relationship_stage': chat_context.relationship_stage,
                    'messages_count': chat_context.messages_count,
                    'detected_interests': chat_context.detected_interests
                }
            
            # Определяем день общения
            day = self._get_relationship_stage_days(chat_context)
            
            # Строим реалистичный промпт
            try:
                system_prompt, user_prompt = self._build_realistic_prompt(
                    context_dict, message_batch, analysis, day
                )
            except Exception as e:
                logger.error(f"Ошибка в _build_realistic_prompt: {e}")
                raise
            
            # Обновляем контекст чата
            self._update_chat_context_from_batch(chat_id, message_batch, analysis)
            
            # Отправляем запрос к OpenAI
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=100,  # Ограничиваем для коротких ответов
                temperature=0.9,  # Повышаем для естественности
                presence_penalty=0.3,  # Избегаем повторений
                frequency_penalty=0.3
            )
            
            generated_text = response.choices[0].message.content.strip()
            
            # Улучшаем текст для реалистичности
            final_text = self._enhance_realism(generated_text)
            
            logger.info(f"✨ Сгенерирован реалистичный ответ: {final_text}")
            return final_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа: {e}")
            return self._get_fallback_response_realistic(message_batch, analysis)
    
    def _enhance_realism(self, text: str) -> str:
        """Улучшение реалистичности ответа"""
        # Убираем излишнюю вежливость
        text = text.replace("Большое спасибо", "Спасибо")
        text = text.replace("Очень интересно", "Интересно")
        text = text.replace("Было бы здорово", "Здорово")
        
        # Добавляем живости
        if random.random() < 0.2:  # 20% шанс
            text = add_random_typo(text)
        
        # Добавляем смайлики иногда
        if random.random() < 0.3 and not ('?' in text):  # 30% для не-вопросов
            if 'здорово' in text.lower() or 'отлично' in text.lower():
                text += ")"
            elif 'интересно' in text.lower():
                text += "."
        
        return text
    
    def _get_fallback_response_realistic(self, message_batch: MessageBatch, analysis: Dict[str, Any]) -> str:
        """Реалистичные fallback ответы"""
        emotion = analysis.get('emotion', 'neutral')
        has_questions = analysis.get('has_questions', False)
        
        if has_questions:
            fallback_responses = [
                "Хороший вопрос) А ты как считаешь?",
                "Сложно сказать однозначно. А у тебя как?",
                "Думаю да. А ты что думаешь?"
            ]
        elif emotion == 'flirty':
            fallback_responses = [
                "Интригуешь) Расскажи подробнее.",
                "Звучит интересно. А что еще?",
                "Любопытно) А ты часто такая загадочная?"
            ]
        elif emotion == 'work':
            fallback_responses = [
                "Понимаю. А нравится работа?",
                "Ясно. Давно в этой сфере?",
                "Интересно. А планы какие?"
            ]
        else:
            fallback_responses = [
                "Понятно) А как у тебя дела?",
                "Хорошо. А что нового?",
                "Ясно. А планы на день какие?"
            ]
        
        return random.choice(fallback_responses)
    
    def _update_chat_context_from_batch(self, chat_id: int, message_batch: MessageBatch, analysis: Dict[str, Any]):
        """Обновление контекста на основе анализа"""
        try:
            # Извлекаем интересы и информацию
            all_text = message_batch.total_text.lower()
            
            # Расширенный анализ интересов
            interest_patterns = {
                'работа_админ': ['администратор', 'магазин', 'продавец'],
                'работа_трейдинг': ['трейдинг', 'акции', 'криптовалюта', 'биржа'],
                'работа_IT': ['программист', 'разработчик', 'айти', 'компьютер'],
                'свободное_время': ['свободное время', 'отдых', 'выходные'],
                'образование': ['университет', 'институт', 'учеба', 'студент'],
                'спорт': ['спорт', 'зал', 'фитнес', 'тренировка'],
                'путешествия': ['путешествия', 'отпуск', 'поездка', 'страна'],
                'встречи': ['созвониться', 'встретиться', 'увидимся', 'свидание']
            }
            
            detected_interests = []
            for interest, patterns in interest_patterns.items():
                if any(pattern in all_text for pattern in patterns):
                    detected_interests.append(interest)
            
            # Определяем стадию отношений на основе тем
            context = db_manager.get_chat_context(chat_id)
            current_stage = context.relationship_stage if context else 'initial'
            
            # Более умное определение стадии
            topics = analysis.get('topics', [])
            if 'встреча' in topics:
                new_stage = 'ready_to_meet'
            elif 'личное' in topics or analysis.get('emotion') == 'flirty':
                new_stage = 'personal'
            elif 'работа' in topics:
                new_stage = 'getting_acquainted'
            elif 'знакомство' in topics:
                new_stage = 'initial'
            else:
                new_stage = current_stage
            
            # Обновляем контекст
            update_data = {}
            if detected_interests:
                existing_interests = []
                if context and context.detected_interests:
                    try:
                        existing_interests = json.loads(context.detected_interests)
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        existing_interests = []
                all_interests = list(set(existing_interests + detected_interests))
                update_data['detected_interests'] = json.dumps(all_interests)
            
            if new_stage != current_stage:
                update_data['relationship_stage'] = new_stage
                logger.info(f"📈 Стадия отношений: {current_stage} → {new_stage}")
            
            if update_data:
                db_manager.update_chat_context(chat_id, **update_data)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления контекста: {e}")
    
    def should_respond(self, chat_id: int, message_batch: MessageBatch) -> bool:
        """Определяем, нужно ли отвечать (для знакомств - почти всегда да)"""
        if not message_batch.messages:
            return False
        
        # В знакомствах отвечаем почти всегда, кроме очень коротких пауз
        last_message = message_batch.messages[-1]
        time_since = (datetime.utcnow() - last_message.created_at).total_seconds()
        
        # Если прошло меньше 30 секунд - возможно она еще пишет
        if time_since < 5:
            logger.debug(f"Пропускаем ответ для чата {chat_id}: прошло только {time_since:.1f}с (нужно 30с)")
            return False  
        
        return True
    
    # Обратная совместимость
    async def generate_response(self, chat_id: int, incoming_message: str) -> Optional[str]:
        """Генерация ответа на одиночное сообщение (legacy)"""
        from ..database.models import Message
        fake_message = Message(
            chat_id=chat_id,
            text=incoming_message,
            is_from_ai=False,
            created_at=datetime.utcnow()
        )
        
        batch = MessageBatch([fake_message])
        return await self.generate_response_for_batch(chat_id, batch)