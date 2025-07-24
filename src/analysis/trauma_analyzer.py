"""
Анализатор травм и эмоционального вовлечения для создания глубокой связи
"""
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from openai import OpenAI
from loguru import logger

from ..config.settings import settings


class TraumaAnalyzer:
    """Анализ эмоциональных травм и генерация естественных реакций"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
        # Истории Стаса для раскрытия
        self.stas_stories = {
            "child_friend_death": {
                "title": "Смерть лучшего друга в детстве",
                "trigger_topics": ["детство", "друзья", "предательство", "смерть", "насилие"],
                "emotional_weight": 9,
                "full_story": """В детстве у нас был свой район, своя компания, свои дворы. И был Влад — мой друг с семи лет. Он был из тех, кто рвётся везде первым: на стройку, в заброшку, на гаражи. Мы с ним постоянно были вместе: школа, приставки, футбол, первые сигареты за гаражами и разговоры про то, как мы будем гонять на байках, когда вырастем.

Всё изменилось летом, когда нам было по 13.

Он связался с двумя ребятами постарше. Я тогда уже чувствовал, что что-то не так: те парни были с мутной репутацией — ходили слухи, что у них проблемы с наркотиками и воровством. Я пытался отговорить его, но у Влада был какой-то свой романтизм — мол, "они просто ищут лёгкие деньги, ничего такого".

Они втянули его в «дело» — ограбить дом родственников одного из них. Сценарий был простой: Влад должен был зайти, разведать, отвлечь. Но он начал сомневаться. Сказал, что не хочет участвовать. Они испугались, что он расскажет. И тогда…

Они перебили ему шею лопатой. Просто так. Затем замотали его в ковёр и выкинули на заброшку за районом, как мусор.

Я узнал об этом только через несколько дней, когда его мать подняла шум и начали искать. Я помню, как мы стояли во дворе и не могли поверить. Он просто исчез. А потом его нашли. Мальчика, с которым я делил тайны, обменивался кассетами и прятался от родителей.

С тех пор у меня внутри остался некий щелчок. Я рано понял, что жизнь может быть жестокой. И что в один день ты можешь потерять того, кто был тебе ближе всех. Это научило меня одному: ценить настоящих людей, отличать ложь от правды и не молчать, если видишь, что кто-то идёт не туда."""
            },
            
            "partner_loss": {
                "title": "Потеря партнерши и ребенка",
                "trigger_topics": ["отношения", "семья", "дети", "потеря", "смерть", "беременность"],
                "emotional_weight": 10,
                "full_story": """Были отношения, из которых должен был вырасти брак. Но выросло что-то совсем другое…

Мы были вместе почти пять лет. Знаешь, из тех отношений, которые не просто про влюблённость, а про настоящее партнёрство: вместе вставали, строили планы, мечтали о доме с окнами на озеро, спорили о чём-то глупом, а потом мирились, потому что знали — дальше жить друг без друга не получится.

В какой-то момент мы поняли, что готовы к семье. Узнали, что будет ребёнок — это было не просто счастье, это был новый виток. Я видел, как она смотрела на УЗИ, как гладила живот, как уже называла его по имени, хотя даже пол ещё не был подтверждён. Мы много смеялись, выбирали имена, покупали детские вещи, перестраивали спальню…

Но всё закончилось в один день.

Роды начались на пару недель раньше. Вроде бы всё шло хорошо — до того момента, пока не стало ясно, что начались внутренние осложнения. Дальше всё было как в тумане: скорая, реанимация, красные лампы, врачи бегают… и тишина. Страшная, абсолютная тишина. Она не выжила. И наш малыш тоже.

Это был крах — как будто мир просто обрушился в чёрную дыру. Я не знал, как дальше дышать, зачем просыпаться, как вообще быть. Снаружи я вроде бы был жив, но внутри меня не осталось никого.

Почти два года ушло на то, чтобы собрать себя по кусочкам. Психотерапия, тишина, разговоры с собой, бессонные ночи, случайные слёзы на улице… Но сегодня я могу это рассказывать — и не плакать. Это не значит, что боль ушла. Она просто теперь не управляет мной. Я живу дальше — и с благодарностью вспоминаю то, что у нас было."""
            }
        }
    
    def analyze_emotional_context(self, conversation_text: str, new_messages: str) -> Dict:
        """Анализ эмоционального контекста и травм"""
        try:
            # ИИ анализ эмоций и травм
            emotional_analysis = self._get_ai_emotional_analysis(conversation_text, new_messages)
            
            # Определяем возможность раскрытия историй Стаса
            story_recommendations = self._analyze_story_sharing_opportunity(
                emotional_analysis, new_messages
            )
            
            result = {
                "emotional_analysis": emotional_analysis,
                "story_recommendations": story_recommendations,
                "trust_level": self._calculate_trust_level(emotional_analysis),
                "emotional_connection": self._calculate_emotional_connection(emotional_analysis),
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"💝 Эмоциональный анализ: доверие {result['trust_level']}/10, "
                       f"связь {result['emotional_connection']}/10")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа травм: {e}")
            return self._get_fallback_emotional_analysis()

    def _get_ai_emotional_analysis(self, history: str, new_messages: str) -> Dict:
        """ИИ анализ эмоционального состояния"""
        try:
            prompt = f"""Проанализируй эмоциональное состояние девушки и уровень доверия в диалоге.

    ИСТОРИЯ ДИАЛОГА:
    {history}

    НОВЫЕ СООБЩЕНИЯ:
    {new_messages}

    ВЕРНИ ТОЛЬКО JSON БЕЗ ОБЕРТКИ:
    {{
        "emotional_openness": 1-10,
        "trust_level": 1-10,
        "vulnerability_shown": 1-10,
        "traumas_shared": ["описание травм если есть"],
        "emotional_triggers": ["темы которые её задевают"],
        "support_needed": true/false,
        "reciprocity_readiness": 1-10,
        "intimacy_level": 1-10,
        "emotional_state": "радость/грусть/злость/нейтрально/смешанно",
        "personal_details_shared": ["личные детали которые рассказала"],
        "family_situation": "что известно о семье",
        "relationship_history": "что известно об отношениях"
    }}

    Ищи признаки:
    - Рассказы о травмах, потерях, боли
    - Семейные проблемы, проблемы в отношениях
    - Готовность делиться личным
    - Потребность в поддержке и понимании
    - Взаимность в раскрытии"""

            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=500
            )

            content = response.choices[0].message.content.strip()
            if not content:
                logger.warning(f"Пустой ответ от OpenAI для эмоционального анализа")
                return self._get_default_emotional_analysis()

            # Очищаем от markdown оберток
            content = self._clean_json_response(content)

            if not content:
                logger.warning(f"Не удалось очистить JSON ответ")
                return self._get_default_emotional_analysis()

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON от OpenAI: {content[:100]}...")
                return self._get_default_emotional_analysis()

        except Exception as e:
            logger.error(f"❌ Ошибка ИИ анализа эмоций: {e}")
            return self._get_default_emotional_analysis()

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
    
    def _analyze_story_sharing_opportunity(self, emotional_analysis: Dict, new_messages: str) -> Dict:
        """Определить возможность поделиться историей Стаса"""
        trust_level = emotional_analysis.get("trust_level", 0)
        vulnerability = emotional_analysis.get("vulnerability_shown", 0)
        traumas_shared = emotional_analysis.get("traumas_shared", [])
        
        # Анализируем какая история подходит
        message_lower = new_messages.lower()
        
        story_scores = {}
        for story_id, story_data in self.stas_stories.items():
            score = 0
            
            # Проверяем триггерные темы
            for trigger in story_data["trigger_topics"]:
                if trigger in message_lower:
                    score += 2
            
            # Бонус за высокое доверие
            if trust_level >= 7:
                score += 3
            
            # Бонус за её открытость
            if vulnerability >= 6:
                score += 2
            
            # Бонус если она делилась травмами
            if traumas_shared:
                score += 4
            
            story_scores[story_id] = score
        
        # Выбираем лучшую историю
        best_story_id = max(story_scores.keys(), key=lambda k: story_scores[k])
        best_score = story_scores[best_story_id]
        
        return {
            "recommended_story": best_story_id if best_score >= 5 else None,
            "story_scores": story_scores,
            "readiness_level": "высокая" if best_score >= 8 else "средняя" if best_score >= 5 else "низкая",
            "sharing_strategy": self._get_sharing_strategy(best_score, best_story_id)
        }
    
    def _get_sharing_strategy(self, score: int, story_id: str) -> str:
        """Стратегия раскрытия истории"""
        if score >= 8:
            return f"Можно поделиться полной историей '{story_id}' - высокий уровень доверия"
        elif score >= 5:
            return f"Можно намекнуть на историю '{story_id}' - проверить реакцию"
        else:
            return "Не время для раскрытия - продолжать развивать доверие"
    
    def generate_trauma_response(self, her_trauma: str, emotional_analysis: Dict) -> str:
        """Генерация естественной реакции на травму"""
        try:
            trust_level = emotional_analysis.get("trust_level", 5)
            
            prompt = f"""Сгенерируй естественный ответ Стаса на травму девушки.

ОНА ПОДЕЛИЛАСЬ: {her_trauma}

УРОВЕНЬ ДОВЕРИЯ: {trust_level}/10

КОНТЕКСТ: Стас 27 лет, криптотрейдер, у него есть две болезненные истории:
1. Смерть лучшего друга в 13 лет (убили)  
2. Потеря партнерши и ребенка при родах

ТРЕБОВАНИЯ:
- Максимально искренняя реакция по-человечески
- Показать сочувствие и понимание
- 1-2 предложения + деликатный вопрос
- Если подходит контекст - намекнуть на свой опыт
- Не давать советы, только поддержка

ПРИМЕРЫ ХОРОШИХ ОТВЕТОВ:
"Сочувствую искренне... У меня тоже была похожая потеря. Как ты справляешься с этим?"
"Понимаю эту боль. Потерял близкого человека в детстве. Отпустило или до сих пор тяжело?"
"Это больно... Знаю что значит потерять того, кто дорог. Есть кто-то рядом кто поддерживает?"

ОТВЕТЬ ОДНИМ СООБЩЕНИЕМ ОТ СТАСА:"""

            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа на травму: {e}")
            return "Сочувствую... Это тяжело. Как ты с этим справляешься?"
    
    def should_share_stas_story(self, story_recommendations: Dict, trust_level: int) -> Tuple[bool, str, str]:
        """Определить нужно ли делиться историей Стаса"""
        recommended_story = story_recommendations.get("recommended_story")
        readiness = story_recommendations.get("readiness_level", "низкая")
        
        if recommended_story and readiness in ["высокая", "средняя"] and trust_level >= 6:
            story_data = self.stas_stories[recommended_story]
            
            if readiness == "высокая":
                return True, recommended_story, story_data["full_story"]
            else:
                # Короткая версия для средней готовности
                short_version = self._get_story_teaser(recommended_story)
                return True, recommended_story, short_version
        
        return False, "", ""
    
    def _get_story_teaser(self, story_id: str) -> str:
        """Короткая версия истории для тестирования реакции"""
        teasers = {
            "child_friend_death": "У меня в детстве был лучший друг... В 13 лет его убили из-за какой-то глупости. До сих пор помню.",
            "partner_loss": "Были серьезные отношения, планировали семью... Но потерял их обоих при родах. Это изменило всё."
        }
        return teasers.get(story_id, "")
    
    def _calculate_trust_level(self, emotional_analysis: Dict) -> int:
        """Расчет уровня доверия"""
        trust = emotional_analysis.get("trust_level", 5)
        openness = emotional_analysis.get("emotional_openness", 5)
        vulnerability = emotional_analysis.get("vulnerability_shown", 5)
        
        return min(10, max(1, (trust + openness + vulnerability) // 3))
    
    def _calculate_emotional_connection(self, emotional_analysis: Dict) -> int:
        """Расчет эмоциональной связи"""
        intimacy = emotional_analysis.get("intimacy_level", 5)
        reciprocity = emotional_analysis.get("reciprocity_readiness", 5)
        support_needed = 2 if emotional_analysis.get("support_needed", False) else 0
        
        return min(10, max(1, (intimacy + reciprocity + support_needed) // 3))
    
    def _get_default_emotional_analysis(self) -> Dict:
        """Базовый анализ эмоций"""
        return {
            "emotional_openness": 5,
            "trust_level": 5,
            "vulnerability_shown": 3,
            "traumas_shared": [],
            "emotional_triggers": [],
            "support_needed": False,
            "reciprocity_readiness": 5,
            "intimacy_level": 3,
            "emotional_state": "нейтрально",
            "personal_details_shared": [],
            "family_situation": "неизвестно",
            "relationship_history": "неизвестно"
        }
    
    def _get_fallback_emotional_analysis(self) -> Dict:
        """Анализ при ошибке"""
        return {
            "emotional_analysis": self._get_default_emotional_analysis(),
            "story_recommendations": {
                "recommended_story": None,
                "story_scores": {},
                "readiness_level": "низкая",
                "sharing_strategy": "Продолжать развивать доверие"
            },
            "trust_level": 5,
            "emotional_connection": 3,
            "analyzed_at": datetime.utcnow().isoformat()
        }