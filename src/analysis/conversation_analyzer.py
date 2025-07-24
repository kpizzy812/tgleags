"""
Центральный анализатор диалогов - координирует все аспекты анализа
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger

from .dialogue_stage_analyzer import DialogueStageAnalyzer
from .financial_analyzer import FinancialAnalyzer
from .trauma_analyzer import TraumaAnalyzer
from ..database.database import db_manager, MessageBatch


class ConversationAnalyzer:
    """Центральный координатор всех анализаторов диалогов"""
    
    def __init__(self):
        self.stage_analyzer = DialogueStageAnalyzer()
        self.financial_analyzer = FinancialAnalyzer()
        self.trauma_analyzer = TraumaAnalyzer()
    
    def analyze_conversation_context(self, chat_id: int, message_batch: MessageBatch) -> Dict:
        """Комплексный анализ контекста диалога"""
        try:
            logger.info(f"🔍 Начинаем комплексный анализ диалога {chat_id}")
            
            # Получаем историю диалога
            conversation_history = db_manager.get_recent_conversation_context(chat_id, limit=100)
            new_messages_text = message_batch.total_text
            
            # Запускаем все анализаторы параллельно
            stage_analysis = self.stage_analyzer.analyze_current_stage(chat_id, message_batch)
            financial_analysis = self.financial_analyzer.analyze_financial_potential(
                conversation_history, new_messages_text
            )
            emotional_analysis = self.trauma_analyzer.analyze_emotional_context(
                conversation_history, new_messages_text
            )
            
            # Комбинируем результаты
            comprehensive_analysis = {
                "chat_id": chat_id,
                "analyzed_at": datetime.utcnow().isoformat(),
                "message_batch_info": {
                    "message_count": len(message_batch.messages),
                    "time_span": message_batch.get_context_summary()
                },
                
                # Результаты анализаторов
                "stage_analysis": stage_analysis,
                "financial_analysis": financial_analysis,
                "emotional_analysis": emotional_analysis,
                
                # Сводные метрики
                "overall_metrics": self._calculate_overall_metrics(
                    stage_analysis, financial_analysis, emotional_analysis
                ),
                
                # Рекомендации по стратегии
                "strategy_recommendations": self._generate_strategy_recommendations(
                    stage_analysis, financial_analysis, emotional_analysis
                )
            }
            
            # Логируем ключевые инсайты
            self._log_key_insights(comprehensive_analysis)
            
            return comprehensive_analysis
            
        except Exception as e:
            logger.error(f"❌ Ошибка комплексного анализа: {e}")
            return self._get_fallback_analysis(chat_id, message_batch)
    
    def _calculate_overall_metrics(self, stage_analysis: Dict, 
                                 financial_analysis: Dict, 
                                 emotional_analysis: Dict) -> Dict:
        """Расчет общих метрик диалога"""
        
        # Прогресс диалога
        stage_progress = stage_analysis.get("stage_completion_percentage", 0)
        dialogue_day = stage_analysis.get("dialogue_day", 1)
        
        # Финансовый потенциал
        financial_score = financial_analysis.get("overall_score", 0)
        readiness_level = financial_analysis.get("readiness_level", "отсутствует")
        
        # Эмоциональная связь
        trust_level = emotional_analysis.get("trust_level", 0)
        emotional_connection = emotional_analysis.get("emotional_connection", 0)
        
        # Общий скор перспективности (0-100)
        overall_prospect_score = self._calculate_prospect_score(
            stage_progress, financial_score, trust_level, dialogue_day
        )
        
        return {
            "dialogue_day": dialogue_day,
            "stage_progress": stage_progress,
            "financial_potential": financial_score,
            "trust_level": trust_level,  
            "emotional_connection": emotional_connection,
            "overall_prospect_score": overall_prospect_score,
            "readiness_assessment": self._assess_overall_readiness(
                stage_analysis, financial_analysis, emotional_analysis
            )
        }
    
    def _calculate_prospect_score(self, stage_progress: int, financial_score: int, 
                                trust_level: int, dialogue_day: int) -> int:
        """Расчет общего скора перспективности диалога"""
        
        # Веса для разных факторов
        weights = {
            "stage_progress": 0.3,
            "financial_potential": 0.4,  # Главный фактор
            "trust_level": 0.2,
            "time_factor": 0.1
        }
        
        # Нормализуем значения к 0-100
        normalized_financial = (financial_score / 10) * 100
        normalized_trust = (trust_level / 10) * 100
        time_factor = min(100, (dialogue_day / 7) * 100)  # 7 дней = 100%
        
        # Рассчитываем взвешенный скор
        weighted_score = (
            stage_progress * weights["stage_progress"] +
            normalized_financial * weights["financial_potential"] +
            normalized_trust * weights["trust_level"] +
            time_factor * weights["time_factor"]
        )
        
        return int(min(100, max(0, weighted_score)))
    
    def _assess_overall_readiness(self, stage_analysis: Dict, 
                                financial_analysis: Dict, 
                                emotional_analysis: Dict) -> Dict:
        """Общая оценка готовности к следующим шагам"""
        
        current_stage = stage_analysis.get("current_stage", "initiation")
        financial_readiness = financial_analysis.get("readiness_level", "отсутствует")
        trust_level = emotional_analysis.get("trust_level", 0)
        
        # Готовность к предложению работы
        work_offer_ready = (
            current_stage in ["diagnosis", "proposal"] and
            financial_readiness in ["высокая", "средняя"] and
            trust_level >= 6
        )
        
        # Готовность к раскрытию историй
        story_sharing_ready = (
            trust_level >= 7 and
            emotional_analysis.get("emotional_analysis", {}).get("vulnerability_shown", 0) >= 6
        )
        
        # Риск потери диалога
        dialogue_risk = self._assess_dialogue_risk(stage_analysis, financial_analysis)
        
        return {
            "ready_for_work_offer": work_offer_ready,
            "ready_for_story_sharing": story_sharing_ready,
            "dialogue_risk_level": dialogue_risk,
            "next_recommended_action": self._get_next_action_recommendation(
                current_stage, financial_readiness, trust_level, work_offer_ready
            )
        }
    
    def _assess_dialogue_risk(self, stage_analysis: Dict, financial_analysis: Dict) -> str:
        """Оценка риска потери диалога"""
        
        crypto_reaction = stage_analysis.get("crypto_reaction", "unknown")
        financial_signals = stage_analysis.get("financial_signals_count", 0)
        dialogue_day = stage_analysis.get("dialogue_day", 1)
        
        # Высокий риск
        if crypto_reaction == "negative":
            return "высокий - негативная реакция на крипто"
        
        if dialogue_day >= 5 and financial_signals == 0:
            return "высокий - нет финансовых сигналов на 5+ день"
        
        # Средний риск  
        if dialogue_day >= 3 and financial_signals <= 1:
            return "средний - мало финансовых сигналов"
        
        # Низкий риск
        if financial_signals >= 2:
            return "низкий - хорошие финансовые сигналы"
        
        return "средний - недостаточно данных"
    
    def _get_next_action_recommendation(self, current_stage: str, financial_readiness: str, 
                                      trust_level: int, work_offer_ready: bool) -> str:
        """Рекомендация следующего действия"""
        
        if work_offer_ready:
            return "Предложить работу/помощь в криптотрейдинге"
        
        if current_stage == "diagnosis" and trust_level >= 7:
            return "Использовать сценарий с отцом в больнице"
        
        if current_stage == "retention" and financial_readiness == "отсутствует":
            return "Активнее выявлять финансовые проблемы"
        
        if current_stage == "initiation":
            return "Узнать работу и реакцию на криптотрейдинг"
        
        if trust_level < 6:
            return "Развивать эмоциональную связь и доверие"
        
        return "Продолжать текущую стратегию"
    
    def _generate_strategy_recommendations(self, stage_analysis: Dict, 
                                         financial_analysis: Dict, 
                                         emotional_analysis: Dict) -> Dict:
        """Генерация рекомендаций по стратегии"""
        
        # Стратегия этапа
        stage_strategy = self.stage_analyzer.get_stage_specific_instructions(stage_analysis)
        
        # Финансовая стратегия
        financial_strategy = self.financial_analyzer.generate_financial_response_strategy(financial_analysis)
        
        # Эмоциональная стратегия
        story_recommendations = emotional_analysis.get("story_recommendations", {})
        
        # Специальные сценарии
        special_scenarios = self._identify_special_scenarios(
            stage_analysis, financial_analysis, emotional_analysis
        )
        
        return {
            "stage_strategy": stage_strategy,
            "financial_strategy": financial_strategy,
            "story_sharing_recommendations": story_recommendations,
            "special_scenarios": special_scenarios,
            "priority_focus": self._determine_priority_focus(
                stage_analysis, financial_analysis, emotional_analysis
            )
        }
    
    def _identify_special_scenarios(self, stage_analysis: Dict, 
                                   financial_analysis: Dict, 
                                   emotional_analysis: Dict) -> List[str]:
        """Определение специальных сценариев"""
        scenarios = []
        
        # Сценарий с отцом
        dialogue_day = stage_analysis.get("dialogue_day", 1)
        trust_level = emotional_analysis.get("trust_level", 0)
        
        if dialogue_day >= 3 and trust_level >= 6:
            scenarios.append("father_hospital_scenario")
        
        # Активное предложение работы
        financial_readiness = financial_analysis.get("readiness_level", "отсутствует")
        if financial_readiness == "высокая":
            scenarios.append("active_work_proposal")
        
        # Риск потери диалога
        crypto_reaction = stage_analysis.get("crypto_reaction", "unknown")
        if crypto_reaction == "negative":
            scenarios.append("dialogue_termination_risk")
        
        return scenarios
    
    def _determine_priority_focus(self, stage_analysis: Dict, 
                                financial_analysis: Dict, 
                                emotional_analysis: Dict) -> str:
        """Определение приоритетного фокуса"""
        
        # Проверяем критические ситуации
        crypto_reaction = stage_analysis.get("crypto_reaction", "unknown")
        if crypto_reaction == "negative":
            return "damage_control"
        
        # Проверяем готовность к предложению
        financial_readiness = financial_analysis.get("readiness_level", "отсутствует")
        if financial_readiness == "высокая":
            return "work_proposal"
        
        # Проверяем эмоциональную связь
        trust_level = emotional_analysis.get("trust_level", 0)
        if trust_level >= 8:
            return "deep_emotional_connection"
        
        # Проверяем финансовые сигналы
        financial_score = financial_analysis.get("overall_score", 0)
        if financial_score <= 3:
            return "financial_signals_detection"
        
        # По умолчанию
        current_stage = stage_analysis.get("current_stage", "initiation")
        return f"stage_progression_{current_stage}"
    
    def _log_key_insights(self, analysis: Dict):
        """Логирование ключевых инсайтов"""
        metrics = analysis.get("overall_metrics", {})
        
        logger.info(f"🎯 Комплексный анализ завершен:")
        logger.info(f"   📊 Общий скор: {metrics.get('overall_prospect_score', 0)}/100")
        logger.info(f"   📈 Этап: {analysis['stage_analysis'].get('current_stage', 'unknown')}")
        logger.info(f"   💰 Финансовый потенциал: {metrics.get('financial_potential', 0)}/10")
        logger.info(f"   🤝 Уровень доверия: {metrics.get('trust_level', 0)}/10")
        logger.info(f"   🎬 Приоритет: {analysis['strategy_recommendations'].get('priority_focus', 'unknown')}")
    
    def _get_fallback_analysis(self, chat_id: int, message_batch: MessageBatch) -> Dict:
        """Базовый анализ при ошибке"""
        return {
            "chat_id": chat_id,
            "analyzed_at": datetime.utcnow().isoformat(),
            "message_batch_info": {
                "message_count": len(message_batch.messages),
                "time_span": "Ошибка анализа"
            },
            "stage_analysis": {"current_stage": "initiation", "dialogue_day": 1},
            "financial_analysis": {"overall_score": 5, "readiness_level": "низкая"},
            "emotional_analysis": {"trust_level": 5, "emotional_connection": 3},
            "overall_metrics": {
                "overall_prospect_score": 30,
                "readiness_assessment": {
                    "ready_for_work_offer": False,
                    "next_recommended_action": "Продолжать знакомство"
                }
            },
            "strategy_recommendations": {
                "priority_focus": "stage_progression_initiation"
            }
        }