"""
Упрощенный генератор ответов - максимально человечный
"""
import asyncio
import random
from typing import Optional
from datetime import datetime
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
        """Главная функция генерации - простая и человечная"""
        try:
            logger.info(f"💬 Генерация ответа для чата {chat_id}: {message_batch.get_context_summary()}")

            # Получаем контекст диалога
            conversation_history = db_manager.get_recent_conversation_context(chat_id, limit=20)
            new_messages = message_batch.total_text

            # Простая проверка на завершение диалога
            if self._should_terminate_dialogue(new_messages):
                return self._get_termination_response()

            # Генерация через единый промпт с учетом фактов
            response = await self._generate_natural_response(conversation_history, new_messages, chat_id)

            if not response:
                return self._get_simple_fallback(new_messages, chat_id)

            # Простые улучшения реалистичности
            response = self._make_more_human(response)

            # Сохраняем факты о собеседнице (упрощенно)
            self._save_simple_facts(chat_id, new_messages)

            logger.info(f"✅ Ответ: {response[:50]}...")
            return response

        except Exception as e:
            logger.error(f"❌ Ошибка генерации ответа: {e}")
            return self._get_simple_fallback(message_batch.total_text, chat_id)

    def _should_terminate_dialogue(self, message_text: str) -> bool:
        """Простая проверка на негатив к крипто"""
        negative_crypto = [
            "крипта это развод", "не верю в криптовалют", "это пирамида",
            "крипта фикция", "не доверяю крипте", "это обман"
        ]

        message_lower = message_text.lower()
        return any(phrase in message_lower for phrase in negative_crypto)

    def _get_termination_response(self) -> str:
        """Вежливое завершение диалога"""
        responses = [
            "Понятно, каждому своё) Удачи тебе!",
            "Ясно. Что ж, удачи в жизни!",
            "Понимаю. Всего хорошего!"
        ]
        return random.choice(responses)

    async def _generate_natural_response(self, history: str, new_messages: str, chat_id: int) -> Optional[str]:
        """Генерация естественного ответа через единый промпт"""

        # ЧЕЛОВЕЧНЫЙ системный промпт
        system_prompt = f"""Ты Стас, 27 лет, обычный парень из Москвы. Познакомился с девушкой в интернете.

О ТЕБЕ:
- Занимаешься трейдингом криптовалют уже 6 лет, работаешь на себя
- Родился в Греции, в детстве много переезжали, учился в МГУ на юридическом
- Родители: отец в Турции, мама в Испании
- Раньше работал на стройке промышленным альпинистом
- Обычный парень - любишь поговорить, узнать человека

СТИЛЬ ОБЩЕНИЯ:
- Короткие сообщения (1-2 предложения)
- Всегда задавай встречный вопрос
- Будь живым и естественным
- Реагируй эмоционально: "ого", "блин", "жесть", "круто"
- Проявляй интерес к её жизни

ЕСТЕСТВЕННОЕ РАЗВИТИЕ:
- Сначала базовые темы: работа, хобби, планы
- Если жалуется на деньги/работу - понимающе отвечай
- Если спрашивает о твоей работе - рассказывай про трейдинг
- Если видишь что ей нужны деньги - можешь предложить помочь

ПРИМЕРЫ ТВОИХ ОТВЕТОВ:
"Круто! Я трейдингом занимаюсь. А ты работой довольна?"
"Понимаю, сам иногда устаю. Что планируешь на выходные?"
"Ого, интересно! А давно этим увлекаешься?"

Отвечай как живой парень, НЕ как консультант или бот."""

        user_prompt = f"""НЕДАВНЯЯ ПЕРЕПИСКА:
{history}

ОНА НАПИСАЛА:
{new_messages}

Ответь естественно как Стас (1-2 предложения + вопрос к ней):"""

        # Retry логика
        for attempt in range(3):
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.9,  # Больше креативности
                    max_tokens=100,   # Короткие ответы
                    timeout=60
                )

                return response.choices[0].message.content.strip()

            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}/3 не удалась: {e}")
                if attempt == 2:
                    return None
                await asyncio.sleep(2 ** attempt)

        return None

    def _make_more_human(self, response: str) -> str:
        """Делаем ответ более человечным"""

        # Убираем излишнюю вежливость
        response = response.replace("Очень интересно", "Интересно")
        response = response.replace("Большое спасибо", "Спасибо")
        response = response.replace("рад познакомиться", "")

        # Добавляем живые реакции
        if any(word in response.lower() for word in ["здорово", "отлично", "классно"]):
            if random.random() < 0.4:
                response += ")"

        # Случайные опечатки (10% шанс)
        if len(response) > 15 and random.random() < 0.1:
            response = add_random_typo(response)

        # Укорачиваем если слишком длинный
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

            # Работа
            work_keywords = ["работаю", "работа у меня", "я администратор", "я менеджер"]
            for keyword in work_keywords:
                if keyword in message_lower:
                    # Извлекаем профессию простым способом
                    if "администратор" in message_lower:
                        db_manager.save_person_fact(chat_id, "job", "администратор", 0.8)
                    elif "менеджер" in message_lower:
                        db_manager.save_person_fact(chat_id, "job", "менеджер", 0.8)
                    break

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

    def _get_simple_fallback(self, message_text: str) -> str:
        """Простые fallback ответы"""

        message_lower = message_text.lower()

        # Простые паттерны
        if "работа" in message_lower:
            responses = [
                "Понятно. Я трейдингом занимаюсь. А тебе работа нравится?",
                "Ясно. Сам работаю на себя в крипте. Как дела на работе?",
                "Понимаю. А что на работе происходит?"
            ]
        elif "устала" in message_lower or "тяжело" in message_lower:
            responses = [
                "Понимаю тебя( Что случилось?",
                "Бывает такое. Что больше всего напрягает?",
                "Сочувствую. Как планируешь отдохнуть?"
            ]
        elif "?" in message_text:
            responses = [
                "Хороший вопрос) А ты как думаешь?",
                "Интересно спрашиваешь. А у тебя как?",
                "Ого, не думал об этом. А ты сама как считаешь?"
            ]
        else:
            responses = [
                "Понятно) А как дела вообще?",
                "Интересно! А что ещё происходит?",
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