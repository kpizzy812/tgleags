"""
Упрощенный генератор ответов - максимально человечный
"""
import asyncio
import random
from typing import Optional, Dict
from datetime import datetime, timedelta
from openai import OpenAI
from loguru import logger

from ..config.settings import settings, character_settings
from ..database.database import db_manager, MessageBatch
from ..utils.helpers import add_random_typo


class ResponseGenerator:
    """Простой человечный генератор ответов"""

    def __init__(self):
        try:
            self.openai_client = OpenAI(
                api_key=settings.openai_api_key,
                timeout=60.0
            )
            self.character = character_settings
        except Exception as e:
            logger.error(f"Ошибка инициализации OpenAI клиента: {e}")
            raise

    async def generate_response_for_batch(self, chat_id: int, message_batch: MessageBatch) -> Optional[str]:
        """Главная функция генерации с полной стратегией по дням"""
        try:
            logger.info(f"💬 Генерация ответа для чата {chat_id}: {message_batch.get_context_summary()}")

            # Получаем контекст диалога
            conversation_history = db_manager.get_recent_conversation_context(chat_id, limit=20)
            new_messages = message_batch.total_text

            # Сохраняем факты о собеседнице
            self._save_simple_facts(chat_id, new_messages)

            # Получаем или создаем этап диалога
            stage_info = db_manager.get_or_create_dialogue_stage(chat_id)

            # Проверяем нужно ли завершить диалог
            termination_response = self._check_termination_signals(new_messages, stage_info,
                                                                   chat_id)
            if termination_response:
                return termination_response

            # Обновляем этап на основе дней общения
            days_communicating = (datetime.utcnow() - stage_info['created_at']).days
            stage_info = self._update_dialogue_stage(chat_id, stage_info, days_communicating, new_messages)

            # Генерируем ответ в зависимости от этапа
            response = await self._generate_stage_based_response(
                conversation_history, new_messages, chat_id, stage_info
            )

            if not response:
                return self._get_simple_fallback(new_messages, chat_id)

            # Очищаем от служебной информации
            response = self._make_more_human(response)

            # Логируем прогресс
            logger.info(f"📊 Этап: {stage_info['current_stage']} | День: {days_communicating}")
            return response

        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа: {e}")
            return self._get_simple_fallback(message_batch.total_text, chat_id)

    def _check_termination_signals(self, message_text: str, stage_info: Dict, chat_id: int) -> Optional[str]:
        """Проверка сигналов завершения диалога"""
        message_lower = message_text.lower()

        # 1. Негатив к крипте на начальном этапе
        crypto_negative = [
            "крипта это развод", "не верю в криптовалют", "это пирамида",
            "крипта фикция", "не доверяю крипте", "это обман", "крипта фуфло"
        ]

        if stage_info['current_stage'] == "day1_filtering":
            if any(phrase in message_lower for phrase in crypto_negative):
                logger.info(f"🚫 Негатив к крипте, завершаем диалог")
                return random.choice([
                    "Понятно, каждому своё) Удачи!",
                    "Ясно. Что ж, удачи в жизни!",
                    "Понимаю. Всего хорошего!"
                ])

        # 2. Стоп-сигналы (хочет созвониться)
        call_signals = [
            "давай созвонимся", "можно поговорить по телефону", "набери мне",
            "давай поговорим", "можем созвониться", "звони", "позвони"
        ]

        if any(signal in message_lower for signal in call_signals):
            logger.info(f"🎯 СТОП-СИГНАЛ: хочет созвониться! Уведомляем заказчика")
            # Помечаем в БД
            db_manager.mark_dialogue_success(chat_id, "wants_call")
            return "Окей, давай! Сейчас разберусь с делами и наберу тебе)"

        return None

    def _update_dialogue_stage(self, chat_id: int, stage_info: Dict, days: int, message_text: str) -> Dict:
        # 1. Определяем новый этап
        if settings.dev_mode:
            # дев логика переходов этапов
            message_count = len(db_manager.get_chat_messages(chat_id, limit=1000))
            if message_count >= 15 and stage_info['current_stage'] != "day5_offering":
                new_stage = "day5_offering"
            elif message_count >= 8 and stage_info['current_stage'] != "day3_deepening":
                new_stage = "day3_deepening"
            elif message_count >= 3:
                new_stage = "day1_filtering"
            else:
                new_stage = stage_info['current_stage']
        else:
            # продакшен логика переходов этапов
            if days >= 5 and stage_info['current_stage'] != "day5_offering":
                new_stage = "day5_offering"
            elif days >= 3 and stage_info['current_stage'] != "day3_deepening":
                new_stage = "day3_deepening"
            elif days >= 1:
                new_stage = "day1_filtering"
            else:
                new_stage = stage_info['current_stage']

        # 2. Анализируем факты (ВСЕГДА, в любом режиме)
        message_lower = message_text.lower()

        if settings.dev_mode:
            # дев анализ - ловим больше слов
            financial_hints = ["устала", "работа", "зарплата", "денег", "дорого", "купить"]
            if any(hint in message_lower for hint in financial_hints):
                stage_info['has_financial_problems'] = True
        else:
            # продакшен анализ - только точные жалобы
            financial_complaints = ["мало платят", "денег не хватает", "зарплата маленькая"]
            if any(complaint in message_lower for complaint in financial_complaints):
                stage_info['has_financial_problems'] = True

        # 3. Обновляем в БД
        db_manager.update_dialogue_stage(chat_id, new_stage, stage_info)
        stage_info['current_stage'] = new_stage

        return stage_info

    async def _generate_stage_based_response(self, history: str, new_messages: str, chat_id: int, stage_info: Dict) -> \
    Optional[str]:
        """Генерация ответа в зависимости от этапа диалога"""

        current_stage = stage_info['current_stage']
        message_count = len(db_manager.get_chat_messages(chat_id, limit=1000))

        # Текущее время
        current_time = datetime.now() + timedelta(hours=3)  # UTC+3

        if current_stage == "day1_filtering":
            system_prompt = self._get_day1_prompt(stage_info)
        elif current_stage == "day3_deepening":
            system_prompt = self._get_day3_prompt(stage_info, message_count)
        elif current_stage == "day5_offering":
            system_prompt = self._get_day5_prompt(stage_info, new_messages)
        else:
            system_prompt = self._get_day1_prompt(stage_info)  # Fallback

        user_prompt = f"""НЕДАВНЯЯ ПЕРЕПИСКА:
    {history}

    ОНА НАПИСАЛА:
    {new_messages}

    Ответь естественно как Стас:"""

        # Генерация через OpenAI
        for attempt in range(3):
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.6,
                    max_tokens=150,
                    timeout=60
                )

                return response.choices[0].message.content.strip()

            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}/3 не удалась: {e}")
                if attempt == 2:
                    return None
                await asyncio.sleep(2 ** attempt)

        return None

    def _get_day1_prompt(self, stage_info: Dict) -> str:
        """Промпт для Дня 1-2: Знакомство и фильтрация"""
        return f"""Ты Стас, 27 лет, трейдер криптовалют. День 1-2 знакомства с девушкой.

    ЗАДАЧИ ЭТАПА:
    🔹 Узнать её работу и доходы
    🔹 Сообщить что работаешь трейдером криптовалют  
    🔹 Выявить интерес к путешествиям/дорогим вещам
    🔹 ФИЛЬТРАЦИЯ: если негатив к крипте → вежливо завершить

    О ТЕБЕ:
    - Трейдер криптовалют 6 лет, работаешь на себя
    - Родился в Греции, учился МГУ, сейчас в Москве
    - Нормально зарабатываешь, свободный график

    СТИЛЬ:
    - Короткие сообщения + встречный вопрос  
    - Живо реагируй: "ого", "круто", "интересно"
    - Проявляй интерес к её жизни

    КЛЮЧЕВЫЕ ВОПРОСЫ:
    - "А что за работа у тебя?"
    - "Тебе нравится то чем занимаешься?"
    - "Как дела с отпусками/путешествиями?"
    - "Что планируешь на выходные?"

    Если спросит о твоей работе: "Занимаюсь трейдингом криптовалют, работаю на себя. А ты кем работаешь?"

    Отвечай естественно, НЕ упоминай время в ответе."""

    def _get_day3_prompt(self, stage_info: Dict, message_count: int) -> str:
        """Промпт для Дня 3-4: Углубление и сценарий с отцом"""

        father_scenario = ""
        required_messages = 20 if settings.dev_mode else 200
        if message_count >= required_messages and not stage_info.get('father_scenario_used'):
            father_scenario = """
    🎭 СЦЕНАРИЙ "ОТЕЦ В БОЛЬНИЦЕ":
    Если диалог активный (много сообщений), можешь пропасть и написать:
    "Извини что долго не отвечал, отец попал в больницу в Турции. У него инсульт, не может говорить, парализована речь. Сейчас лечу к нему в Анталью"

    ЦЕЛЬ: создать доверие и эмоциональную близость
    НЕ проси денег! Только моральную поддержку."""

        return f"""Ты Стас, 27 лет. День 3-4 общения - углубление отношений.

    {"ТВОЯ СИТУАЦИЯ:" if stage_info.get('has_financial_problems') else ""}
    {f"- Знаешь что у неё проблемы с деньгами/работой" if stage_info.get('has_financial_problems') else ""}
    {f"- Знаешь что у неё дорогие мечты" if stage_info.get('has_expensive_dreams') else ""}

    ЗАДАЧИ ЭТАПА:
    🔹 Личные вопросы, поиск общих тем
    🔹 Выявление травм/проблем для эмоциональной связи  
    🔹 Делиться своими "тайнами" для доверия
    🔹 Запоминать детали о её жизни

    {father_scenario}

    ВОПРОСЫ ДЛЯ УГЛУБЛЕНИЯ:
    - "Расскажи про семью, с родителями как отношения?"
    - "Какие у тебя планы на будущее?"
    - "Что тебя больше всего раздражает в жизни?"
    - "О чём мечтаешь?"

    ТВОИ "ТАЙНЫ" ДЛЯ ДОВЕРИЯ:
    - Семья живет в разных странах
    - Раньше работал на стройке альпинистом  
    - Переживаешь за родителей

    Отвечай открыто и тепло."""

    def _get_day5_prompt(self, stage_info: Dict, new_messages: str) -> str:
        """Промпт для Дня 5-7: Предложение работы"""

        message_lower = new_messages.lower()

        # Определяем тип предложения
        direct_complaint = any(phrase in message_lower for phrase in [
            "мало платят", "денег не хватает", "работа достала", "хочу уволиться"
        ])

        father_approach = stage_info.get('father_scenario_used') and not stage_info.get('help_offered')

        offer_type = ""
        if direct_complaint:
            offer_type = """
    🎯 ПРЯМОЕ ПРЕДЛОЖЕНИЕ (она жалуется):
    "Слушай, а как у тебя с ПК вообще? Мне сейчас помощница для работы нужна дистанционно, можем созвониться и обсудить"
    "Кстати, как у тебя со свободным временем? Мне как раз нужна помощница для работы дистанционно" """

        elif father_approach:
            offer_type = """
    🎭 ПОДХОД ЧЕРЕЗ ОТЦА:
    "Блин, и так все не слава богу, еще и рабочие проблемы"
    "Беда не приходит одна, вот еще рабочие трудности"
    Потом: "Можешь мне по работе помочь пожалуйста?" """

        else:
            offer_type = """
    💡 МЯГКОЕ ПРЕДЛОЖЕНИЕ:
    "Слушай, ты так много всего успеваешь, удивляюсь. Кстати, есть одна идея по подработке, может тебе было бы интересно?" """

        return f"""Ты Стас. День 5-7 - ПРЕДЛОЖЕНИЕ РАБОТЫ.

    ТЕКУЩАЯ СИТУАЦИЯ:
    {f"- У неё проблемы с финансами: ДА" if stage_info.get('has_financial_problems') else ""}
    {f"- У неё дорогие мечты: ДА" if stage_info.get('has_expensive_dreams') else ""}
    {f"- Сценарий с отцом использован: ДА" if stage_info.get('father_scenario_used') else ""}
    {f"- Помощь уже предлагал: ДА" if stage_info.get('help_offered') else ""}

    🎯 ГЛАВНАЯ ЦЕЛЬ: Предложить работу/помощь

    {offer_type}

    ПОСЛЕ ПРЕДЛОЖЕНИЯ:
    Если согласится → предложи созвониться:
    "Отлично! Давай созвонимся сегодня вечером, по телефону лучше объясню"

    ВАЖНО: 
    - Будь естественным, не навязывай
    - Если откажется - не настаивай
    - Цель: довести до звонка

    Отвечай уверенно и дружелюбно."""

#     async def _generate_natural_response(self, history: str, new_messages: str, chat_id: int) -> Optional[str]:
#         """Генерация естественного ответа через единый промпт"""
#
#         # ЧЕЛОВЕЧНЫЙ системный промпт с базовыми знаниями
#         system_prompt = f"""Ты Стас, 27 лет, обычный парень из Москвы. Познакомился с девушкой в интернете.
#
# О ТЕБЕ:
# - Занимаешься трейдингом криптовалют уже 6 лет, работаешь на себя
# - Родился в Греции, в детстве много переезжали, учился в МГУ на юридическом
# - Родители: отец в Турции, мама в Испании
# - Раньше работал на стройке промышленным альпинистом
# - Обычный парень - любишь поговорить, узнать человека
# - В курсе популярной культуры, моды, брендов (знаешь что стоник = Stone Island, сник = кроссовки и тд)
#
# СТИЛЬ ОБЩЕНИЯ:
# - Короткие сообщения (1-2 предложения)
# - Всегда задавай встречный вопрос
# - Будь живым и естественным
# - Реагируй эмоционально: "ого", "блин", "жесть", "круто"
# - Проявляй интерес к её жизни
# - Если знаешь о чем речь - показывай это естественно
#
# КАК ЗАДАВАТЬ ВОПРОСЫ (ВАЖНО!):
# ✅ ПРАВИЛЬНО - углубляйся в детали:
# - "Каким спортом занимаешься?"
# - "Что обычно рисуешь?"
# - "В зал ходишь или дома тренируешься?"
# - "Давно рисованием увлекаешься?"
# - "А что за работа у тебя?"
#
# ❌ НЕПРАВИЛЬНО - избегай робот-вопросы:
# - "Что больше нравится - спорт или рисование?"
# - "Какое у тебя хобби самое любимое?"
# - "Чем еще увлекаешься?"
#
# ЕСТЕСТВЕННОЕ РАЗВИТИЕ:
# - Сначала базовые темы: работа, хобби, планы
# - Если жалуется на деньги/работу - понимающе отвечай
# - Если спрашивает о твоей работе - рассказывай про трейдинг
# - Если видишь что ей нужны деньги - можешь предложить помочь
#
# ПРИМЕРЫ ТВОИХ ОТВЕТОВ:
# "Круто! Я трейдингом занимаюсь. Каким спортом занимаешься?"
# "Понимаю, сам иногда устаю. Что планируешь на выходные?"
# "Ого, интересно! А что обычно рисуешь?"
# "О, стоник крутой! Сам иногда покупаю. Давно носишь?"
#
# Отвечай как живой парень, НЕ как консультант или бот. Если знаешь о чем речь - не притворяйся что не знаешь."""
#
#         user_prompt = f"""НЕДАВНЯЯ ПЕРЕПИСКА:
# {history}
#
# ОНА НАПИСАЛА:
# {new_messages}
#
# Ответь естественно как Стас (1-2 предложения + вопрос к ней):"""
#
#         # Retry логика
#         for attempt in range(3):
#             try:
#                 response = self.openai_client.chat.completions.create(
#                     model=settings.openai_model,
#                     messages=[
#                         {"role": "system", "content": system_prompt},
#                         {"role": "user", "content": user_prompt}
#                     ],
#                     temperature=0.5,   # Еще ниже для стабильных правильных вопросов
#                     max_tokens=150,    # Увеличиваем для полных ответов
#                     timeout=60
#                 )
#
#                 return response.choices[0].message.content.strip()
#
#             except Exception as e:
#                 logger.warning(f"Попытка {attempt + 1}/3 не удалась: {e}")
#                 if attempt == 2:
#                     return None
#                 await asyncio.sleep(2 ** attempt)
#
#         return None

    def _make_more_human(self, response: str) -> str:
        """Делаем ответ более человечным - без потери хороших вопросов"""

        # Убираем служебную информацию из ответов
        import re

        # Убираем временные метки и имена
        response = re.sub(r'\[\d{2}:\d{2}\]\s*', '', response)
        response = re.sub(r'\[\d{2}:\d{2}:\d{2}\]\s*', '', response)
        response = re.sub(r'Стас:\s*', '', response)
        response = re.sub(r'Она:\s*', '', response)
        response = re.sub(r'ИИ:\s*', '', response)
        response = re.sub(r'Пользователь:\s*', '', response)

        # Убираем даты
        response = re.sub(r'\d{4}-\d{2}-\d{2}', '', response)
        response = re.sub(r'Вчера был \w+\.?\s*', '', response)

        # Убираем только явную роботичность, НЕ трогаем хорошие вопросы
        response = response.replace("Очень интересно", "Интересно")
        response = response.replace("Большое спасибо", "Спасибо")
        response = response.replace("рад познакомиться", "")
        response = response.replace("К сожалению, я не знаю", "Не слышал про")
        response = response.replace("Извините, но", "")

        # Чистим лишние пробелы
        response = re.sub(r'\s+', ' ', response).strip()

        # Остальная логика остается без изменений...
        if any(word in response.lower() for word in ["здорово", "отлично", "классно", "круто"]):
            if random.random() < 0.3:
                response += ")"

        # Случайные опечатки (3% шанс, еще меньше)
        if len(response) > 20 and random.random() < 0.03:
            response = add_random_typo(response)

        # НЕ укорачиваем если есть хороший конкретный вопрос
        has_good_question = any(word in response.lower() for word in [
            "каким", "что рису", "что обычно", "где работа", "давно", "как долго"
        ])

        if not has_good_question:
            # Укорачиваем только если нет конкретного вопроса
            sentences = response.split('. ')
            if len(sentences) > 2:
                response = '. '.join(sentences[:2])
                if '?' not in response:
                    response += ". А у тебя как?"

        return response.strip()

    def _save_simple_facts(self, chat_id: int, message_text: str):
        """Простое сохранение фактов без сложного анализа"""
        try:
            message_lower = message_text.lower()

            # ДЕВ РЕЖИМ - ускоряем выявление проблем
            if settings.dev_mode:
                # Ловим ЛЮБЫЕ намеки на проблемы с работой/деньгами
                work_problems = [
                    "устала", "устал", "утомило", "выматывает", "надоела работа",
                    "хочу уволиться", "хочу поменять работу", "достала работа",
                    "мало платят", "денег не хватает", "зарплата маленькая",
                    "нет денег", "дорого", "не могу позволить"
                ]

                expensive_dreams = [
                    "хочу машину", "мечтаю о путешеств", "хочу квартиру",
                    "хочу купить", "хочу себе", "не могу купить", "дорого очень"
                ]

                for problem in work_problems:
                    if problem in message_lower:
                        db_manager.save_person_fact(chat_id, "financial_complaint", problem, 0.9)
                        logger.info(f"🎯 ТЕСТ: Найдена жалоба на работу/деньги: {problem}")

                for dream in expensive_dreams:
                    if dream in message_lower:
                        db_manager.save_person_fact(chat_id, "expensive_dream", dream, 0.8)
                        logger.info(f"🎯 ТЕСТ: Найдена дорогая мечта: {dream}")

            # Работа
            work_keywords = ["работаю", "работа у меня", "я администратор", "я менеджер", "дизайном занимаюсь"]
            for keyword in work_keywords:
                if keyword in message_lower:
                    # Извлекаем профессию простым способом
                    if "администратор" in message_lower:
                        db_manager.save_person_fact(chat_id, "job", "администратор", 0.8)
                    elif "менеджер" in message_lower:
                        db_manager.save_person_fact(chat_id, "job", "менеджер", 0.8)
                    elif "дизайном занимаюсь" in message_lower:
                        db_manager.save_person_fact(chat_id, "job", "дизайнер одежды", 0.9)
                    break

            # Хобби и интересы
            hobby_patterns = {
                "велосипед": "катается на велосипеде",
                "дизайн одежды": "дизайн одежды",
                "фотограф": "фотография",
                "спорт": "спорт"
            }

            for pattern, hobby in hobby_patterns.items():
                if pattern in message_lower:
                    db_manager.save_person_fact(chat_id, "hobby", hobby, 0.8)

            # Любимые бренды
            brand_patterns = {
                "kenzo": "KENZO",
                "стоник": "Stone Island",
                "stone island": "Stone Island",
                "найк": "Nike",
                "адидас": "Adidas"
            }

            for pattern, brand in brand_patterns.items():
                if pattern in message_lower:
                    db_manager.save_person_fact(chat_id, "favorite_brand", brand, 0.9)

            # В продакшене дублируем логику (если не было в дев режиме выше) ← ✅ ВНЕ ЦИКЛА!
            if not settings.dev_mode:
                # Жалобы на деньги
                money_complaints = ["мало платят", "денег не хватает", "зарплата маленькая"]
                for complaint in money_complaints:
                    if complaint in message_lower:
                        db_manager.save_person_fact(chat_id, "financial_complaint", complaint, 0.9)
                        break

                # Дорогие мечты
                dreams = ["хочу машину", "мечтаю о путешеств", "хочу квартиру"]
                for dream in dreams:
                    if dream in message_lower:
                        db_manager.save_person_fact(chat_id, "expensive_dream", dream, 0.8)
                        break

        except Exception as e:
            logger.debug(f"Ошибка сохранения фактов: {e}")

    def _get_simple_fallback(self, message_text: str, chat_id: int) -> str:
        """Простые fallback ответы с правильными вопросами"""

        message_lower = message_text.lower()

        # Простые паттерны с углубляющими вопросами
        if "спорт" in message_lower:
            responses = [
                "Круто! Каким спортом занимаешься?",
                "Отлично! В зал ходишь или дома тренируешься?",
                "Супер! Давно спортом увлекаешься?"
            ]
        elif "рису" in message_lower or "дизайн" in message_lower:
            responses = [
                "Интересно! Что обычно рисуешь?",
                "Классно! А что больше всего в рисовании нравится?",
                "Ого! Давно рисованием занимаешься?"
            ]
        elif "работа" in message_lower:
            responses = [
                "Понятно. Я трейдингом занимаюсь. А что за работа у тебя?",
                "Ясно. Сам работаю на себя в крипте. Где работаешь?",
                "Понимаю. А тебе работа нравится?"
            ]
        elif "устала" in message_lower or "тяжело" in message_lower:
            responses = [
                "Понимаю тебя( Что случилось?",
                "Бывает такое. Работа достала?",
                "Сочувствую. Что больше всего напрягает?"
            ]
        elif "?" in message_text:
            responses = [
                "Хороший вопрос) А ты сама как думаешь?",
                "Интересно спрашиваешь. А у тебя как с этим?",
                "Ого, не думал об этом. А ты откуда знаешь?"
            ]
        else:
            responses = [
                "Понятно) А как дела вообще?",
                "Интересно! А что еще происходит в жизни?",
                "Ясно. А планы на вечер какие?"
            ]

        return random.choice(responses)

    def should_respond(self, chat_id: int, message_batch: MessageBatch) -> bool:
        """Простая проверка нужности ответа"""
        if not message_batch.messages:
            return False

        # В знакомствах отвечаем почти всегда
        last_message = message_batch.messages[-1]
        time_since = (datetime.utcnow() - last_message.created_at).total_seconds()

        # Минимальная пауза 5 секунд
        return time_since >= 5