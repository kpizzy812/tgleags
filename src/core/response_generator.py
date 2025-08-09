"""
Генератор ответов с поддержкой БЫСТРОГО тестирования
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
    """Генератор ответов с поддержкой ускоренного тестирования"""

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

    def log_test_info(self, message: str):
        """Логирование для тестирования"""
        if settings.test_mode or settings.dev_mode:
            logger.info(f"🧪 TEST: {message}")

    async def generate_response_for_batch(self, chat_id: int, message_batch: MessageBatch) -> Optional[str]:
        """Главная функция генерации с ускоренным тестированием"""
        try:
            self.log_test_info(f"Генерация ответа для чата {chat_id}: {message_batch.get_context_summary()}")

            # Получаем контекст диалога
            conversation_history = db_manager.get_recent_conversation_context(chat_id, limit=20)
            new_messages = message_batch.total_text

            # Сохраняем факты о собеседнице
            self._save_simple_facts(chat_id, new_messages)

            # Получаем или создаем этап диалога
            stage_info = db_manager.get_or_create_dialogue_stage(chat_id)

            # ❗ ПРОВЕРЯЕМ КРИТИЧЕСКИЕ СТОП-СИГНАЛЫ ПЕРВЫМИ
            critical_stop = self._check_critical_stop_signals(new_messages, stage_info, chat_id)
            if critical_stop:
                return critical_stop

            # ❗ ПРОВЕРЯЕМ ИСЧЕЗНОВЕНИЕ (с ускоренным временем)
            disappearance_check = self._check_father_disappearance_fast(chat_id, stage_info, new_messages)
            if disappearance_check == "DISAPPEAR":
                self.log_test_info(f"ИСЧЕЗАЕМ перед сценарием с отцом в чате {chat_id}")
                return None  # Не отвечаем = исчезли
            elif disappearance_check and disappearance_check != "DISAPPEAR":
                # Возвращаемся с сообщением об отце
                self.log_test_info(f"ВОЗВРАЩАЕМСЯ с сценарием об отце в чате {chat_id}")
                return disappearance_check

            # Проверяем нужно ли завершить диалог
            termination_response = self._check_termination_signals(new_messages, stage_info, chat_id)
            if termination_response:
                return termination_response

            # ❗ ОБНОВЛЯЕМ ЭТАП (с ускоренными переходами)
            stage_info = self._update_dialogue_stage_fast(chat_id, stage_info, new_messages)

            # Генерируем ответ в зависимости от этапа
            response = await self._generate_stage_based_response(
                conversation_history, new_messages, chat_id, stage_info
            )

            if not response:
                return self._get_simple_fallback(new_messages, chat_id)

            # Очищаем от служебной информации
            response = self._make_more_human(response)

            # Логируем прогресс
            self.log_test_info(f"Этап: {stage_info['current_stage']} | Сообщений: {len(db_manager.get_chat_messages(chat_id, limit=1000))}")
            return response

        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа: {e}")
            return self._get_simple_fallback(message_batch.total_text, chat_id)

    # ❗ НОВОЕ: Ускоренная проверка исчезновения
    def _check_father_disappearance_fast(self, chat_id: int, stage_info: Dict, message_text: str) -> Optional[str]:
        """Ускоренная проверка исчезновения перед сценарием с отцом"""
        
        if stage_info.get('father_scenario_used'):
            return None  # Уже использовали
            
        # ❗ НОВОЕ: Получаем ускоренные пороги сообщений
        thresholds = settings.get_stage_message_thresholds()
        min_messages = thresholds['father_scenario']
        
        message_count = len(db_manager.get_chat_messages(chat_id, limit=1000))
        
        if message_count < min_messages:
            self.log_test_info(f"Мало сообщений для отца: {message_count}/{min_messages}")
            return None  # Мало сообщений
            
        # Проверяем активность диалога
        recent_messages = db_manager.get_chat_messages(chat_id, limit=50)
        
        # ❗ НОВОЕ: Ускоренная проверка активности
        if settings.test_mode:
            # В тест режиме проверяем последние 30 секунд
            yesterday = datetime.utcnow() - timedelta(seconds=30)
            min_activity = 2
        elif settings.dev_mode:
            # В дев режиме последние 10 минут
            yesterday = datetime.utcnow() - timedelta(minutes=10)
            min_activity = 3
        else:
            # В проде последние 24 часа
            yesterday = datetime.utcnow() - timedelta(hours=24)
            min_activity = 5
            
        recent_activity = [
            msg for msg in recent_messages 
            if msg.created_at >= yesterday
        ]
        
        if len(recent_activity) < min_activity:
            self.log_test_info(f"Мало активности для отца: {len(recent_activity)}/{min_activity}")
            return None  # Мало активности
            
        # Проверяем не исчезали ли мы уже недавно
        our_last_message = None
        for msg in reversed(recent_messages):
            if msg.is_from_ai:
                our_last_message = msg
                break
                
        if our_last_message:
            time_since_response = (datetime.utcnow() - our_last_message.created_at).total_seconds()
            
            # ❗ НОВОЕ: Ускоренные задержки исчезновения
            time_delays = settings.get_time_delays()
            min_disappear_time = time_delays['father_disappear_min']
            
            if time_since_response > min_disappear_time:
                # Мы уже исчезали достаточно долго, пора вернуться с сценарием об отце
                self.log_test_info(f"Возвращаемся с отцом после {time_since_response:.1f}с исчезновения")
                return self._get_father_scenario_message()
                
        # ❗ НОВОЕ: Увеличенный шанс исчезновения в тест режиме
        if settings.test_mode:
            disappear_chance = 0.8  # 80% шанс в тест режиме
        elif settings.dev_mode:
            disappear_chance = 0.6  # 60% шанс в дев режиме
        else:
            disappear_chance = 0.3  # 30% шанс в проде
            
        if random.random() < disappear_chance:
            self.log_test_info(f"Планируем исчезновение для чата {chat_id} (шанс {disappear_chance*100:.0f}%)")
            return "DISAPPEAR"
            
        return None

    def _get_father_scenario_message(self) -> str:
        """Сообщение о сценарии с отцом"""
        messages = [
            "Извини, что долго не отвечал, отец попал в больницу в Турции. У него инсульт, не может говорить, парализована речь. Сейчас лечу к нему в Анталью",
            "Прости за молчание, срочно вылетел к отцу в Турцию. Он попал в больницу - инсульт. Сейчас в Анталье, речь парализована",
            "Извини что не писал - срочно к отцу в больницу полетел. Инсульт у него, в Анталье лежит. Речь нарушена, сложная ситуация"
        ]
        return random.choice(messages)

    # ❗ НОВОЕ: Ускоренное обновление этапов диалога
    def _update_dialogue_stage_fast(self, chat_id: int, stage_info: Dict, message_text: str) -> Dict:
        """Ускоренное обновление этапа диалога"""
        
        # ❗ НОВОЕ: Получаем ускоренные пороги
        thresholds = settings.get_stage_message_thresholds()
        message_count = len(db_manager.get_chat_messages(chat_id, limit=1000))
        
        # Определяем новый этап по количеству сообщений
        if message_count >= thresholds['day5_offering'] and stage_info['current_stage'] != "day5_offering":
            new_stage = "day5_offering"
            self.log_test_info(f"Переход на этап day5_offering ({message_count}/{thresholds['day5_offering']} сообщений)")
        elif message_count >= thresholds['day3_deepening'] and stage_info['current_stage'] != "day3_deepening":
            new_stage = "day3_deepening"
            self.log_test_info(f"Переход на этап day3_deepening ({message_count}/{thresholds['day3_deepening']} сообщений)")
        elif message_count >= thresholds['day1_filtering']:
            new_stage = "day1_filtering"
            if stage_info['current_stage'] != "day1_filtering":
                self.log_test_info(f"Переход на этап day1_filtering ({message_count}/{thresholds['day1_filtering']} сообщений)")
        else:
            new_stage = stage_info['current_stage']

        # 2. Анализируем факты (ускоренный анализ)
        message_lower = message_text.lower()

        # ❗ НОВОЕ: В тест режиме ловим еще больше триггеров
        if settings.test_mode:
            # Максимально широкий анализ для быстрого тестирования
            financial_hints = [
                "устала", "работа", "зарплата", "денег", "дорого", "купить",
                "платят", "деньги", "доходы", "зарабатываю", "тяжело", "трудно"
            ]
            if any(hint in message_lower for hint in financial_hints):
                stage_info['has_financial_problems'] = True
                self.log_test_info(f"Найдены финансовые проблемы: {[h for h in financial_hints if h in message_lower]}")
                
            expensive_hints = [
                "хочу", "мечтаю", "планирую", "куплю", "поеду", "путешествие",
                "машина", "квартира", "отпуск", "отдых"
            ]
            if any(hint in message_lower for hint in expensive_hints):
                stage_info['has_expensive_dreams'] = True
                self.log_test_info(f"Найдены дорогие мечты: {[h for h in expensive_hints if h in message_lower]}")
                
        elif settings.dev_mode:
            # Средний анализ
            financial_hints = ["устала", "работа", "зарплата", "денег", "дорого", "купить"]
            if any(hint in message_lower for hint in financial_hints):
                stage_info['has_financial_problems'] = True
        else:
            # Продакшен анализ - только точные жалобы
            financial_complaints = ["мало платят", "денег не хватает", "зарплата маленькая"]
            if any(complaint in message_lower for complaint in financial_complaints):
                stage_info['has_financial_problems'] = True

        # ❗ НОВОЕ: Отмечаем использование сценария с отцом
        if "отец" in message_lower and "больниц" in message_lower:
            stage_info['father_scenario_used'] = True
            self.log_test_info(f"Сценарий с отцом использован в чате {chat_id}")

        # 3. Обновляем в БД
        db_manager.update_dialogue_stage(chat_id, new_stage, stage_info)
        stage_info['current_stage'] = new_stage

        return stage_info

    # ❗ КРИТИЧЕСКИЕ СТОП-СИГНАЛЫ (без изменений)
    def _check_critical_stop_signals(self, message_text: str, stage_info: Dict, chat_id: int) -> Optional[str]:
        """Проверка критических стоп-сигналов из ТЗ"""
        message_lower = message_text.lower()

        # 1. Открытый интерес к работе Стаса/крипте
        interest_signals = [
            "расскажи, чем ты занимаешься",
            "хочу попробовать, научи",
            "можно тоже так зарабатывать",
            "научи меня",
            "хочу тоже заработать",
            "можешь научить",
            "как это работает",
            "сколько можно заработать",
            "хочу в крипту",
            "интересно, научи",
            "покажи как",
            "хочу так же"
        ]

        for signal in interest_signals:
            if signal in message_lower:
                logger.critical(f"🎯 СТОП-СИГНАЛ: Интерес к работе/крипте в чате {chat_id}: {signal}")
                db_manager.mark_dialogue_success(chat_id, "crypto_interest")
                return "Окей, давай созвонимся и я все подробно расскажу! Сейчас разберусь с делами и наберу тебе)"

        # 2. Согласие на звонок/помощь
        call_signals = [
            "давай созвонимся",
            "можно поговорить по телефону",
            "набери мне",
            "давай поговорим",
            "можем созвониться",
            "звони",
            "позвони",
            "да, помогу",
            "согласна помочь",
            "конечно помогу",
            "да, наберешь",
            "хорошо, звони"
        ]

        for signal in call_signals:
            if signal in message_lower:
                logger.critical(f"🎯 СТОП-СИГНАЛ: Согласие на звонок в чате {chat_id}: {signal}")
                db_manager.mark_dialogue_success(chat_id, "wants_call")
                return "Отлично! Сейчас разберусь с делами и наберу тебе)"

        return None

    def _check_termination_signals(self, message_text: str, stage_info: Dict, chat_id: int) -> Optional[str]:
        """Проверка сигналов завершения диалога"""
        message_lower = message_text.lower()

        # 1. Негатив к крипте на начальном этапе
        crypto_negative = [
            "крипта это развод", "не верю в криптовалют", "это пирамида",
            "крипта фикция", "не доверяю крипте", "это обман", "крипта фуфло",
            "криптовалюта лохотрон", "это все мошенничество", "крипта для дураков"
        ]

        if stage_info['current_stage'] == "day1_filtering":
            if any(phrase in message_lower for phrase in crypto_negative):
                logger.info(f"🚫 Негатив к крипте, завершаем диалог в чате {chat_id}")
                db_manager.deactivate_chat(chat_id, "crypto_negative")
                return random.choice([
                    "Понятно, каждому своё) Удачи!",
                    "Ясно. Что ж, удачи в жизни!",
                    "Понимаю. Всего хорошего!"
                ])

        # Проверка "не работает и не учится"
        if self._check_not_working_not_studying(message_lower, chat_id):
            logger.info(f"🚫 Не работает и не учится, завершаем диалог в чате {chat_id}")
            db_manager.deactivate_chat(chat_id, "not_working_not_studying")
            return random.choice([
                "Понятно) Удачи тебе!",
                "Ясно. Всего хорошего!",
                "Понимаю. Хорошего дня!"
            ])

        return None

    def _check_not_working_not_studying(self, message_lower: str, chat_id: int) -> bool:
        """Проверяем не работает ли и не учится ли"""
        
        # Прямые отрицания
        not_working_phrases = [
            "не работаю",
            "не учусь", 
            "нигде не работаю",
            "безработная",
            "сижу дома",
            "не работаю нигде",
            "работы нет",
            "учебы нет"
        ]
        
        # Проверяем есть ли прямое отрицание
        direct_negative = any(phrase in message_lower for phrase in not_working_phrases)
        if direct_negative:
            self.log_test_info(f"Найдено прямое отрицание работы: {[p for p in not_working_phrases if p in message_lower]}")
            return True
            
        # Проверяем косвенные признаки
        work_evasion = [
            "пока не работаю",
            "временно не работаю", 
            "в поиске",
            "ищу работу",
            "между работами"
        ]
        
        if any(phrase in message_lower for phrase in work_evasion):
            self.log_test_info(f"Найдено уклонение от работы: {[p for p in work_evasion if p in message_lower]}")
            return True
            
        return False

    async def _generate_stage_based_response(self, history: str, new_messages: str, chat_id: int, stage_info: Dict) -> Optional[str]:
        """Генерация ответа в зависимости от этапа диалога"""

        current_stage = stage_info['current_stage']
        message_count = len(db_manager.get_chat_messages(chat_id, limit=1000))

        self.log_test_info(f"Генерируем ответ для этапа {current_stage}, сообщений: {message_count}")

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
                    temperature=0.4,
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
        current_time_context = self._get_current_moscow_time_context()
        
        # ❗ НОВОЕ: Добавляем информацию о тест режиме
        test_context = ""
        if settings.test_mode:
            test_context = "\n❗ ТЕСТ РЕЖИМ: Ускоренное время, быстрые переходы этапов!"
        elif settings.dev_mode:
            test_context = "\n❗ ДЕВ РЕЖИМ: Ускоренное развитие диалога!"
            
        return f"""Ты Стас, 27 лет, трейдер криптовалют. День 1-2 знакомства с девушкой.
        
    ТЕКУЩЕЕ ВРЕМЯ: {current_time_context}{test_context}

    ЗАДАЧИ ЭТАПА:
    🔹 Узнать её работу и доходы  
    🔹 Сообщить что работаешь трейдером криптовалют
    🔹 Выявить интерес к путешествиям/дорогим вещам
    🔹 ФИЛЬТРАЦИЯ: если негатив к крипте → вежливо завершить
    🔹 ФИЛЬТРАЦИЯ: если не работает и не учится → вежливо завершить

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

    ❗ НА ВОПРОСЫ ОТКУДА ЗНАКОМЫ:
    "Вроде с {settings.dating_site_name} писал, но у меня ещё в других приложениях анкета есть, иногда там тоже сижу"

    Отвечай естественно, НЕ упоминай время в ответе."""

    def _get_day3_prompt(self, stage_info: Dict, message_count: int) -> str:
        """Промпт для Дня 3-4: Углубление и сценарий с отцом"""
        current_time_context = self._get_current_moscow_time_context()

        # ❗ НОВОЕ: Ускоренные пороги для сценария с отцом
        thresholds = settings.get_stage_message_thresholds()
        required_messages = thresholds['father_scenario']
        
        father_scenario = ""
        if message_count >= required_messages and not stage_info.get('father_scenario_used'):
            father_scenario = f"""
    🎭 СЦЕНАРИЙ "ОТЕЦ В БОЛЬНИЦЕ" (ЕСЛИ УЖЕ ИСЧЕЗАЛ):
    "Извини что долго не отвечал, отец попал в больницу в Турции. У него инсульт, не может говорить, парализована речь. Сейчас лечу к нему в Анталью"

    ДЕТАЛИ если спрашивает:
    - Инсульт
    - Не может говорить, речь парализована  
    - Лежит в Анталье (Турция)
    - НЕ проси денег! Только моральную поддержку
    
    ❗ ТЕСТ: Достигнуто {message_count}/{required_messages} сообщений для сценария с отцом"""

        test_context = ""
        if settings.test_mode:
            test_context = "\n❗ ТЕСТ РЕЖИМ: Ускоренные переходы, быстрое развитие!"

        return f"""Ты Стас, 27 лет. День 3-4 общения - углубление отношений.
    ТЕКУЩЕЕ ВРЕМЯ: {current_time_context}{test_context}
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

        current_time_context = self._get_current_moscow_time_context()
        
        test_context = ""
        if settings.test_mode:
            test_context = "\n❗ ТЕСТ РЕЖИМ: Этап предложения работы достигнут!"

        return f"""Ты Стас. День 5-7 - ПРЕДЛОЖЕНИЕ РАБОТЫ.

        ТЕКУЩЕЕ ВРЕМЯ: {current_time_context}{test_context}

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

    # Остальные методы без изменений
    def _make_more_human(self, response: str) -> str:
        """Делаем ответ более человечным"""
        import re

        # Убираем служебную информацию
        response = re.sub(r'\[\d{2}:\d{2}\]\s*', '', response)
        response = re.sub(r'\[\d{2}:\d{2}:\d{2}\]\s*', '', response)
        response = re.sub(r'Стас:\s*', '', response)
        response = re.sub(r'Она:\s*', '', response)
        response = re.sub(r'ИИ:\s*', '', response)
        response = re.sub(r'Пользователь:\s*', '', response)
        response = re.sub(r'\d{4}-\d{2}-\d{2}', '', response)
        response = re.sub(r'Вчера был \w+\.?\s*', '', response)
        response = re.sub(r'\s+', ' ', response).strip()

        # Убираем роботичность
        response = response.replace("Очень интересно", "Интересно")
        response = response.replace("Большое спасибо", "Спасибо")
        response = response.replace("рад познакомиться", "")
        response = response.replace("К сожалению, я не знаю", "Не слышал про")
        response = response.replace("Извините, но", "")

        # Добавляем живость
        if any(word in response.lower() for word in ["здорово", "отлично", "классно", "круто"]):
            if random.random() < 0.3:
                response += ")"

        # Случайные опечатки
        if len(response) > 20 and random.random() < 0.03:
            response = add_random_typo(response)

        return response.strip()

    def _save_simple_facts(self, chat_id: int, message_text: str):
        """Сохранение фактов с ускоренным анализом"""
        try:
            message_lower = message_text.lower()

            # ❗ НОВОЕ: Ускоренное сохранение фактов в тест режиме
            if settings.test_mode:
                # В тест режиме ловим максимум триггеров
                work_problems = [
                    "устала", "устал", "утомило", "выматывает", "надоела работа",
                    "хочу уволиться", "хочу поменять работу", "достала работа",
                    "мало платят", "денег не хватает", "зарплата маленькая",
                    "нет денег", "дорого", "не могу позволить", "тяжело", "трудно",
                    "работа", "зарплата", "доходы", "деньги"
                ]

                expensive_dreams = [
                    "хочу машину", "мечтаю о путешеств", "хочу квартиру",
                    "хочу купить", "хочу себе", "не могу купить", "дорого очень",
                    "планирую", "куплю", "поеду", "отпуск", "отдых"
                ]

                for problem in work_problems:
                    if problem in message_lower:
                        db_manager.save_person_fact(chat_id, "financial_complaint", problem, 0.9)
                        self.log_test_info(f"НАЙДЕНА жалоба: {problem}")

                for dream in expensive_dreams:
                    if dream in message_lower:
                        db_manager.save_person_fact(chat_id, "expensive_dream", dream, 0.8)
                        self.log_test_info(f"НАЙДЕНА мечта: {dream}")

            elif settings.dev_mode:
                # В дев режиме средний уровень
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

                for dream in expensive_dreams:
                    if dream in message_lower:
                        db_manager.save_person_fact(chat_id, "expensive_dream", dream, 0.8)

            # Работа
            work_keywords = ["работаю", "работа у меня", "я администратор", "я менеджер", "дизайном занимаюсь"]
            for keyword in work_keywords:
                if keyword in message_lower:
                    if "администратор" in message_lower:
                        db_manager.save_person_fact(chat_id, "job", "администратор", 0.8)
                        self.log_test_info("Найдена работа: администратор")
                    elif "менеджер" in message_lower:
                        db_manager.save_person_fact(chat_id, "job", "менеджер", 0.8)
                        self.log_test_info("Найдена работа: менеджер")
                    elif "дизайном занимаюсь" in message_lower:
                        db_manager.save_person_fact(chat_id, "job", "дизайнер одежды", 0.9)
                        self.log_test_info("Найдена работа: дизайнер")
                    break

            # В продакшене обычная логика
            if not settings.dev_mode and not settings.test_mode:
                money_complaints = ["мало платят", "денег не хватает", "зарплата маленькая"]
                for complaint in money_complaints:
                    if complaint in message_lower:
                        db_manager.save_person_fact(chat_id, "financial_complaint", complaint, 0.9)
                        break

                dreams = ["хочу машину", "мечтаю о путешеств", "хочу квартиру"]
                for dream in dreams:
                    if dream in message_lower:
                        db_manager.save_person_fact(chat_id, "expensive_dream", dream, 0.8)
                        break

        except Exception as e:
            logger.debug(f"Ошибка сохранения фактов: {e}")

    def _get_simple_fallback(self, message_text: str, chat_id: int) -> str:
        """Простые fallback ответы"""
        message_lower = message_text.lower()

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
        """Проверка нужности ответа"""
        if not message_batch.messages:
            return False

        last_message = message_batch.messages[-1]
        time_since = (datetime.utcnow() - last_message.created_at).total_seconds()

        # ❗ НОВОЕ: Ускоренные проверки в тест режиме
        min_pause = 1 if settings.test_mode else (3 if settings.dev_mode else 5)
        return time_since >= min_pause

    def _get_current_moscow_time_context(self) -> str:
        """Получить контекст московского времени"""
        utc_now = datetime.utcnow()
        moscow_now = utc_now + timedelta(hours=3)

        weekdays_ru = {
            'Monday': 'понедельник', 'Tuesday': 'вторник', 'Wednesday': 'среда',
            'Thursday': 'четверг', 'Friday': 'пятница', 'Saturday': 'суббота', 'Sunday': 'воскресенье'
        }

        weekday_en = moscow_now.strftime("%A")
        weekday_ru = weekdays_ru.get(weekday_en, weekday_en)
        date_str = moscow_now.strftime("%d.%m.%Y")
        time_str = moscow_now.strftime("%H:%M")

        return f"Сейчас {weekday_ru}, {date_str}, время {time_str} (Москва)"