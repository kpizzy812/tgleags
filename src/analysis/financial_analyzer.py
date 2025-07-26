"""
Анализатор финансовых потребностей и возможностей заработка
"""
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from openai import OpenAI
from loguru import logger

from ..config.settings import settings


class FinancialAnalyzer:
    """Анализ финансовых потребностей и готовности к заработку"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
        # Паттерны финансовых жалоб
        self.complaint_patterns = {
            "salary_low": [
                r"мало плат\w+", r"маленькая зарплата", r"копейки плат\w+",
                r"денег не хватает", r"нет денег", r"бедно жив\w+"
            ],
            "work_dissatisfaction": [
                r"работа достала", r"надоела работа", r"устала от работ\w+",
                r"начальник достал", r"хочу уволиться"
            ],
            "expensive_desires": [
                r"хочу машину", r"мечтаю о машин\w+", r"хочу путешествовать",
                r"мечтаю путешествовать", r"хочу квартиру", r"нет денег на"
            ]
        }
        
        # Позитивные финансовые индикаторы
        self.positive_patterns = [
            r"хорошо зарабатываю", r"достаточно денег", r"не жалуюсь",
            r"всё устраивает", r"довольна зарплатой"
        ]
    
    def analyze_financial_potential(self, conversation_text: str, new_messages: str) -> Dict:
        """Анализ финансового потенциала собеседницы"""
        try:
            # Комбинируем весь текст для анализа
            full_text = f"{conversation_text}\n{new_messages}".lower()
            
            # Подсчитываем паттерны
            complaint_scores = self._count_complaint_patterns(full_text)
            desire_signals = self._extract_expensive_desires(full_text)
            
            # Анализируем через ИИ для более глубокого понимания
            ai_analysis = self._get_ai_financial_analysis(conversation_text, new_messages)
            
            # Объединяем результаты
            result = {
                "complaint_scores": complaint_scores,
                "expensive_desires": desire_signals,
                "ai_analysis": ai_analysis,
                "overall_score": self._calculate_overall_score(complaint_scores, ai_analysis),
                "readiness_level": self._determine_readiness_level(complaint_scores, ai_analysis),
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"💰 Финансовый анализ: {result['overall_score']}/10, "
                       f"готовность: {result['readiness_level']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка финансового анализа: {e}")
            return self._get_fallback_financial_analysis()
    
    def _count_complaint_patterns(self, text: str) -> Dict[str, int]:
        """Подсчет паттернов жалоб"""
        scores = {}
        
        for category, patterns in self.complaint_patterns.items():
            count = 0
            for pattern in patterns:
                count += len(re.findall(pattern, text))
            scores[category] = count
        
        return scores
    
    def _extract_expensive_desires(self, text: str) -> List[str]:
        """Извлечение дорогих желаний"""
        desires = []
        
        desire_keywords = {
            "машина": ["машин", "авто", "bmw", "мерседес", "права"],
            "путешествия": ["путешеств", "отпуск", "мальдив", "турци", "европ"],
            "недвижимость": ["квартир", "дом", "ремонт", "ипотек"],
            "образование": ["курсы", "учеба", "образование", "английский"],
            "красота": ["косметолог", "процедур", "салон", "пластик"]
        }
        
        for category, keywords in desire_keywords.items():
            if any(keyword in text for keyword in keywords):
                desires.append(category)
        
        return desires

    def _get_ai_financial_analysis(self, history: str, new_messages: str) -> Dict:
        """ИИ анализ финансового состояния"""
        try:
            prompt = f"""Проанализируй финансовое состояние девушки по диалогу.

    ИСТОРИЯ ДИАЛОГА:
    {history}

    НОВЫЕ СООБЩЕНИЯ:  
    {new_messages}

    ВЕРНИ ТОЛЬКО JSON БЕЗ ОБЕРТКИ:
    {{
        "financial_stress_level": 1-10,
        "job_satisfaction": 1-10,
        "openness_to_opportunities": 1-10,
        "money_complaints_detected": ["конкретные жалобы"],
        "expensive_dreams_mentioned": ["мечты о дорогих вещах"],
        "work_problems": ["проблемы на работе"],
        "potential_motivation": "что может мотивировать к подработке",
        "readiness_indicators": ["индикаторы готовности"],
        "red_flags": ["настораживающие моменты"]
    }}

    Ищи:
    - Жалобы на зарплату, нехватку денег
    - Желания дорогих вещей (машины, путешествия, квартиры)
    - Недовольство работой или начальством
    - Мечты о лучшей жизни
    - Готовность к дополнительному заработку"""

            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=400
            )

            content = response.choices[0].message.content.strip()
            if not content:
                logger.warning(f"Пустой ответ от OpenAI для финансового анализа")
                return self._get_default_financial_analysis()

            # Очищаем от markdown оберток
            content = self._clean_json_response(content)

            if not content:
                logger.warning(f"Не удалось очистить JSON ответ")
                return self._get_default_financial_analysis()

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON от OpenAI: {content[:100]}...")
                return self._get_default_financial_analysis()

        except Exception as e:
            logger.error(f"❌ Ошибка ИИ анализа финансов: {e}")
            return {
                "financial_stress_level": 5,
                "job_satisfaction": 5,
                "openness_to_opportunities": 5,
                "money_complaints_detected": [],
                "expensive_dreams_mentioned": [],
                "work_problems": [],
                "potential_motivation": "Не определено",
                "readiness_indicators": [],
                "red_flags": []
            }

    def _clean_json_response(self, content: str) -> str:
        """Очистка ответа OpenAI от markdown оберток"""
        # Убираем markdown обертки
        content = content.replace('```json', '').replace('```', '')

        # Убираем лишние пробелы и переносы
        content = content.strip()

        # Если это не JSON, возвращаем пустую строку
        if not content.startswith('{'):
            return ""

        return content

    def _get_default_financial_analysis(self) -> Dict:
        """Базовый финансовый анализ"""
        return {
            "financial_stress_level": 5,
            "job_satisfaction": 5,
            "openness_to_opportunities": 5,
            "money_complaints_detected": [],
            "expensive_dreams_mentioned": [],
            "work_problems": [],
            "potential_motivation": "Не определено",
            "readiness_indicators": [],
            "red_flags": []
        }

    def _calculate_overall_score(self, complaint_scores: Dict, ai_analysis: Dict) -> int:
        """Расчет общего финансового скора (1-10)"""
        # Защита от None значений
        pattern_score = sum(v for v in complaint_scores.values() if v is not None) * 2

        # Правильная защита от None из OpenAI
        ai_stress = ai_analysis.get("financial_stress_level") or 5
        ai_openness = ai_analysis.get("openness_to_opportunities") or 5

        # Приводим к int
        pattern_score = int(pattern_score)
        ai_stress = int(ai_stress)
        ai_openness = int(ai_openness)

        # Комбинированный скор
        combined_score = min(10, (pattern_score + ai_stress + ai_openness) // 3)

        return max(1, combined_score)

    def _determine_readiness_level(self, complaint_scores: Dict, ai_analysis: Dict) -> str:
        """Определение уровня готовности к предложению"""
        # Защита от None в complaint_scores
        total_complaints = sum(v for v in complaint_scores.values() if v is not None)

        # Защита от None из OpenAI - правильный способ
        stress_level = ai_analysis.get("financial_stress_level") or 5
        openness = ai_analysis.get("openness_to_opportunities") or 5

        # Убеждаемся что всё int
        total_complaints = int(total_complaints)
        stress_level = int(stress_level)
        openness = int(openness)

        if total_complaints >= 3 and stress_level >= 7 and openness >= 7:
            return "высокая"
        elif total_complaints >= 2 and stress_level >= 5 and openness >= 6:
            return "средняя"
        elif total_complaints >= 1 or stress_level >= 6:
            return "низкая"
        else:
            return "отсутствует"
    
    def _get_fallback_financial_analysis(self) -> Dict:
        """Базовый анализ при ошибке"""
        return {
            "complaint_scores": {"salary_low": 0, "work_dissatisfaction": 0, "expensive_desires": 0},
            "expensive_desires": [],
            "ai_analysis": {
                "financial_stress_level": 5,
                "job_satisfaction": 5,
                "openness_to_opportunities": 5,
                "money_complaints_detected": [],
                "expensive_dreams_mentioned": [],
                "work_problems": [],
                "potential_motivation": "Не определено",
                "readiness_indicators": [],
                "red_flags": []
            },
            "overall_score": 5,
            "readiness_level": "низкая",
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    def generate_financial_response_strategy(self, financial_analysis: Dict) -> str:
        """Генерация стратегии ответа на основе финансового анализа"""
        readiness = financial_analysis.get("readiness_level", "низкая")
        complaints = financial_analysis.get("complaint_scores", {})
        desires = financial_analysis.get("expensive_desires", [])
        
        if readiness == "высокая":
            return """ВЫСОКАЯ ГОТОВНОСТЬ:
- Активно интересуйся её финансовой ситуацией
- Делись своими успехами в трейдинге
- Подготавливай к предложению работы
- Подчеркивай возможности дополнительного заработка"""
        
        elif readiness == "средняя":
            return """СРЕДНЯЯ ГОТОВНОСТЬ:
- Мягко выявляй финансовые проблемы
- Показывай понимание её ситуации
- Рассказывай о своем финансовом успехе
- Создавай базу для будущего предложения"""
        
        elif readiness == "низкая":
            return """НИЗКАЯ ГОТОВНОСТЬ:
- Не форсируй финансовые темы
- Продолжай общее знакомство
- Ищи признаки недовольства работой
- Развивай доверие и эмоциональную связь"""
        
        else:
            return """ГОТОВНОСТЬ ОТСУТСТВУЕТ:
- Сосредоточься на общем общении
- Не упоминай деньги и заработок
- Развивай личные темы
- Ищи другие точки соприкосновения"""
    
    def should_make_work_offer(self, financial_analysis: Dict, dialogue_stage: str) -> Tuple[bool, str]:
        """Определить готовность к предложению работы"""
        readiness = financial_analysis.get("readiness_level", "отсутствует")
        overall_score = financial_analysis.get("overall_score", 0)
        
        # Условия для предложения
        if (dialogue_stage == "proposal" and 
            readiness in ["высокая", "средняя"] and 
            overall_score >= 6):
            
            return True, f"Готова к предложению: {readiness} готовность, скор {overall_score}/10"
        
        elif readiness == "высокая" and overall_score >= 8:
            return True, f"Срочно готова: очень высокие показатели"
        
        else:
            return False, f"Не готова: {readiness} готовность, скор {overall_score}/10"