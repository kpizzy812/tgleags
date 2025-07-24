"""
Улучшенный генератор ответов с модульной архитектурой анализа
"""
import json
from typing import Optional, Dict, Tuple
from datetime import datetime
from openai import OpenAI
from loguru import logger

from ..config.settings import settings, character_settings
from ..database.database import db_manager, MessageBatch
from ..analysis.conversation_analyzer import ConversationAnalyzer
from ..utils.helpers import add_random_typo


class ResponseGenerator:
    """Улучшенный генератор ответов под цели заказчика"""
    
    def __init__(self):
        try:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)
            self.character = character_settings
            self.conversation_analyzer = ConversationAnalyzer()
        except Exception as e:
            logger.error(f"Ошибка инициализации OpenAI клиента: {e}")
            raise
    
    async def generate_response_for_batch(self, chat_id: int, message_batch: MessageBatch) -> Optional[str]:
        """Главная функция генерации ответа с комплексным анализом"""
        try:
            logger.info(f"🎯 Генерация ответа для чата {chat_id}: {message_batch.get_context_summary()}")
            
            # 1. КОМПЛЕКСНЫЙ АНАЛИЗ ДИАЛОГА
            conversation_analysis = self.conversation_analyzer.analyze_conversation_context(
                chat_id, message_batch
            )
            
            # 2. ПРОВЕРКА КРИТИЧЕСКИХ СИТУАЦИЙ
            critical_response = self._handle_critical_situations(conversation_analysis)
            if critical_response:
                return critical_response
            
            # 3. ГЕНЕРАЦИЯ СТРАТЕГИЧЕСКОГО ОТВЕТА
            strategic_response = await self._generate_strategic_response(
                chat_id, message_batch, conversation_analysis
            )
            
            # 4. УЛУЧШЕНИЕ РЕАЛИСТИЧНОСТИ
            final_response = self._enhance_response_realism(strategic_response)
            
            # 5. ОБНОВЛЕНИЕ КОНТЕКСТА
            self._update_conversation_context(chat_id, conversation_analysis)
            
            logger.info(f"✨ Ответ сгенерирован: {final_response[:50]}...")
            return final_response
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа: {e}")
            return self._get_fallback_response(message_batch)
    
    def _handle_critical_situations(self, analysis: Dict) -> Optional[str]:
        """Обработка критических ситуаций"""
        
        stage_analysis = analysis.get("stage_analysis", {})
        crypto_reaction = stage_analysis.get("crypto_reaction", "unknown")
        
        # Негативная реакция на криптотрейдинг - готовимся завершить диалог
        if crypto_reaction == "negative":
            logger.warning("🚨 Негативная реакция на крипто - завершение диалога")
            return "Понятно, каждому своё) Удачи тебе!"
        
        # Проверяем специальные сценарии
        special_scenarios = analysis.get("strategy_recommendations", {}).get("special_scenarios", [])
        
        if "dialogue_termination_risk" in special_scenarios:
            logger.warning("⚠️ Высокий риск потери диалога")
            # Возвращаем None чтобы продолжить обычную генерацию с осторожностью
        
        return None
    
    async def _generate_strategic_response(self, chat_id: int, message_batch: MessageBatch, 
                                         analysis: Dict) -> str:
        """Генерация стратегического ответа на основе анализа"""
        
        # Определяем тип ответа на основе анализа
        response_type = self._determine_response_type(analysis)
        
        if response_type == "trauma_response":
            return await self._generate_trauma_response(analysis)
        elif response_type == "financial_exploration":
            return await self._generate_financial_exploration_response(analysis)
        elif response_type == "work_proposal":
            return await self._generate_work_proposal_response(analysis)
        elif response_type == "father_scenario":
            return await self._generate_father_scenario_response(analysis)
        else:
            return await self._generate_standard_response(chat_id, message_batch, analysis)
    
    def _determine_response_type(self, analysis: Dict) -> str:
        """Определение типа ответа на основе анализа"""
        
        # Приоритет по важности
        priority_focus = analysis.get("strategy_recommendations", {}).get("priority_focus", "")
        
        if "work_proposal" in priority_focus:
            return "work_proposal"
        
        # Проверяем готовность к раскрытию историй
        readiness = analysis.get("overall_metrics", {}).get("readiness_assessment", {})
        if readiness.get("ready_for_story_sharing", False):
            return "trauma_response"
        
        # Проверяем специальные сценарии
        special_scenarios = analysis.get("strategy_recommendations", {}).get("special_scenarios", [])
        if "father_hospital_scenario" in special_scenarios:
            return "father_scenario"
        
        # Проверяем фокус на финансах
        if "financial_signals_detection" in priority_focus:
            return "financial_exploration"
        
        return "standard_response"
    
    async def _generate_trauma_response(self, analysis: Dict) -> str:
        """Генерация ответа на травму с возможным раскрытием истории"""
        
        emotional_analysis = analysis.get("emotional_analysis", {})
        trauma_analyzer = self.conversation_analyzer.trauma_analyzer
        
        # Получаем рекомендации по раскрытию историй
        story_recommendations = emotional_analysis.get("story_recommendations", {})
        trust_level = emotional_analysis.get("trust_level", 0)
        
        # Проверяем нужно ли делиться историей
        should_share, story_id, story_content = trauma_analyzer.should_share_stas_story(
            story_recommendations, trust_level
        )
        
        if should_share:
            logger.info(f"💔 Делимся историей: {story_id}")
            return story_content
        else:
            # Генерируем поддерживающий ответ
            her_trauma = "Она поделилась болезненным опытом"  # Упростим для примера
            return trauma_analyzer.generate_trauma_response(her_trauma, emotional_analysis)
    
    async def _generate_financial_exploration_response(self, analysis: Dict) -> str:
        """Генерация ответа для выявления финансовых проблем"""
        
        stage_analysis = analysis.get("stage_analysis", {})
        dialogue_day = stage_analysis.get("dialogue_day", 1)
        
        # Строим промпт для выявления финансовых проблем
        prompt = f"""Ты Стас, день {dialogue_day} знакомства. ЦЕЛЬ: мягко выявить финансовые проблемы девушки.

СТРАТЕГИЯ:
- Задавай вопросы о работе, зарплате, планах
- Делись своими успехами в криптотрейдинге  
- Выявляй жалобы на деньги
- Интересуйся дорогими мечтами (машины, путешествия)

АНАЛИЗ ДИАЛОГА: {analysis.get('strategy_recommendations', {}).get('financial_strategy', '')}

ОТВЕТЬ от лица Стаса (1-2 предложения + встречный вопрос):"""

        response = self.openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()
    
    async def _generate_work_proposal_response(self, analysis: Dict) -> str:
        """Генерация предложения работы"""
        
        financial_analysis = analysis.get("financial_analysis", {})
        readiness_level = financial_analysis.get("readiness_level", "низкая")
        
        logger.info(f"💼 Предлагаем работу с готовностью: {readiness_level}")
        
        if readiness_level == "высокая":
            return "Слушай, у меня есть идея как подзаработать в криптосфере. Интересно? Могу по телефону объяснить детали."
        else:
            return "Знаешь, у меня есть мысли как можно дополнительно заработать. Не хочешь обсудить?"
    
    async def _generate_father_scenario_response(self, analysis: Dict) -> str:
        """Генерация сценария с отцом в больнице"""
        
        emotional_analysis = analysis.get("emotional_analysis", {})
        trust_level = emotional_analysis.get("trust_level", 0)
        
        if trust_level >= 7:
            return ("Извини что долго не писал... Отец в больнице в Турции, инсульт. "
                   "Не может говорить, врачи борются. Тяжело очень.")
        else:
            return "Извини за молчание, семейные проблемы. Как у тебя дела?"
    
    async def _generate_standard_response(self, chat_id: int, message_batch: MessageBatch, 
                                        analysis: Dict) -> str:
        """Стандартная генерация ответа"""
        
        # Получаем инструкции для текущего этапа
        stage_strategy = analysis.get("strategy_recommendations", {}).get("stage_strategy", "")
        
        # Строим контекст диалога
        conversation_history = db_manager.get_recent_conversation_context(chat_id, limit=20)
        
        # Обновленный системный промпт под цели заказчика
        system_prompt = self._build_updated_system_prompt(analysis)
        
        user_prompt = f"""НЕДАВНЯЯ ИСТОРИЯ:
{conversation_history}

НОВЫЕ СООБЩЕНИЯ:
{message_batch.total_text}

СТРАТЕГИЯ ЭТАПА:
{stage_strategy}

АНАЛИЗ ГОТОВНОСТИ:
{analysis.get('overall_metrics', {}).get('readiness_assessment', {}).get('next_recommended_action', '')}

ОТВЕТЬ от лица Стаса (1-2 предложения + встречный вопрос):"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.8,
            max_tokens=120
        )
        
        return response.choices[0].message.content.strip()
    
    def _build_updated_system_prompt(self, analysis: Dict) -> str:
        """Построение обновленного системного промпта"""
        
        stage_analysis = analysis.get("stage_analysis", {})
        current_stage = stage_analysis.get("current_stage", "initiation")
        dialogue_day = stage_analysis.get("dialogue_day", 1)
        
        return f"""Ты {self.character.name}, {self.character.age}-летний криптотрейдер. Познакомился с девушкой на сайте знакомств.

ИСТИННАЯ ЦЕЛЬ: Через эмоциональную связь выявить финансовые проблемы и предложить работу в криптотрейдинге.

ТЕКУЩИЙ ЭТАП: {current_stage.upper()} (День {dialogue_day})

БИОГРАФИЯ: {self.character.background_story}

СТРАТЕГИЯ ПО ЭТАПАМ:
- ИНИЦИАЦИЯ: Узнать работу, проверить реакцию на крипто, выявить дорогие интересы
- УДЕРЖАНИЕ: Углублять общение, находить общие темы
- ДИАГНОСТИКА: Выявлять финансовые жалобы, создавать эмоциональную связь
- ПРЕДЛОЖЕНИЕ: Предлагать помощь/работу в криптосфере

КРИТИЧЕСКИ ВАЖНО:
- Короткие ответы (1-2 предложения)
- ВСЕГДА встречный вопрос
- Отслеживай реакцию на криптотрейдинг (если негативная - готовься завершить)
- Выявляй жалобы на деньги/работу
- Реагируй на травмы максимально по-человечески
- Помни всё что она рассказывает

ИСТОРИИ ДЛЯ РАСКРЫТИЯ (при высоком доверии):
1. Смерть лучшего друга в 13 лет
2. Потеря партнерши и ребенка при родах

ЗАПРЕЩЕНО:
- Длинные сообщения
- Формальность
- Игнорирование финансовых сигналов
- Преждевременные предложения работы"""
    
    def _enhance_response_realism(self, response: str) -> str:
        """Улучшение реалистичности ответа"""
        
        # Убираем излишнюю вежливость
        response = response.replace("Большое спасибо", "Спасибо")
        response = response.replace("Очень интересно", "Интересно")
        
        # Добавляем случайные опечатки (20% шанс)
        if len(response) > 20 and response.count('.') <= 2:  # Только для коротких ответов
            import random
            if random.random() < 0.2:
                response = add_random_typo(response)
        
        # Добавляем эмотиконы иногда
        import random
        if random.random() < 0.3:
            if any(word in response.lower() for word in ['здорово', 'отлично', 'классно']):
                response += ")"
        
        return response
    
    def _update_conversation_context(self, chat_id: int, analysis: Dict):
        """Обновление контекста диалога на основе анализа"""
        
        try:
            # Извлекаем ключевые факты для обновления
            stage_analysis = analysis.get("stage_analysis", {})
            financial_analysis = analysis.get("financial_analysis", {})
            emotional_analysis = analysis.get("emotional_analysis", {})
            
            # Подготавливаем данные для обновления
            update_data = {}
            
            # Обновляем стадию отношений
            current_stage = stage_analysis.get("current_stage", "initial")
            if current_stage != "initial":
                update_data["relationship_stage"] = current_stage
            
            # Обновляем обнаруженные интересы (финансовые и эмоциональные)
            detected_interests = []
            
            # Финансовые интересы
            expensive_desires = financial_analysis.get("expensive_desires", [])
            if expensive_desires:
                detected_interests.extend([f"желание_{desire}" for desire in expensive_desires])
            
            # Жалобы на финансы
            money_complaints = financial_analysis.get("ai_analysis", {}).get("money_complaints_detected", [])
            if money_complaints:
                detected_interests.extend([f"жалоба_{complaint}" for complaint in money_complaints])
            
            # Эмоциональные темы
            traumas_shared = emotional_analysis.get("emotional_analysis", {}).get("traumas_shared", [])
            if traumas_shared:
                detected_interests.extend([f"травма_{trauma}" for trauma in traumas_shared])
            
            if detected_interests:
                # Получаем существующие интересы
                context = db_manager.get_chat_context(chat_id)
                existing_interests = []
                if context and context.detected_interests:
                    try:
                        existing_interests = json.loads(context.detected_interests)
                    except json.JSONDecodeError:
                        existing_interests = []
                
                # Объединяем интересы
                all_interests = list(set(existing_interests + detected_interests))
                update_data["detected_interests"] = json.dumps(all_interests)
            
            # Обновляем контекст если есть изменения
            if update_data:
                db_manager.update_chat_context(chat_id, **update_data)
                logger.debug(f"📝 Контекст чата {chat_id} обновлен: {list(update_data.keys())}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления контекста: {e}")
    
    def _get_fallback_response(self, message_batch: MessageBatch) -> str:
        """Резервный ответ при ошибке"""
        
        # Простой анализ для fallback
        message_text = message_batch.total_text.lower()
        
        if any(word in message_text for word in ['работа', 'работаю', 'зарплата']):
            return "Интересно! Я трейдингом криптовалют занимаюсь. А ты работой довольна?"
        
        elif any(word in message_text for word in ['устала', 'тяжело', 'проблемы']):
            return "Понимаю тебя. У всех бывают сложные периоды. Что больше всего беспокоит?"
        
        elif '?' in message_text:
            return "Хороший вопрос) Сам иногда об этом думаю. А ты как считаешь?"
        
        else:
            return "Понятно. А расскажи о своих планах на будущее?"
    
    def should_respond(self, chat_id: int, message_batch: MessageBatch) -> bool:
        """Определение необходимости ответа (почти всегда да для знакомств)"""
        
        if not message_batch.messages:
            return False
        
        # В знакомствах отвечаем почти всегда
        last_message = message_batch.messages[-1]
        time_since = (datetime.utcnow() - last_message.created_at).total_seconds()
        
        # Минимальная пауза для реалистичности
        if time_since < 3:
            return False
        
        return True