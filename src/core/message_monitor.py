"""
Мониторинг сообщений с поддержкой БЫСТРОГО тестирования
"""
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

from ..config.settings import settings
from ..database.database import db_manager, MessageBatch
from ..database.models import Chat
from .telegram_client import TelegramAIClient
from .response_generator import ResponseGenerator


class MessageMonitor:
    """Мониторинг с поддержкой ускоренного тестирования"""

    def __init__(self):
        self.telegram_client = TelegramAIClient()
        self.response_generator = ResponseGenerator()
        self.is_monitoring = False

        # Простое отслеживание последних сообщений
        self.last_processed_message_ids: Dict[int, int] = {}

        # Простая очередь ответов
        self.response_queue: List[Dict] = []

        # ❗ Остановленные чаты (переданные человеку)
        self.stopped_chats: set = set()

        # ❗ НОВОЕ: Для быстрого тестирования - виртуальное время
        self.test_start_time = datetime.utcnow()
        self.virtual_time_offset = 0  # Секунды от старта теста

        # Базовая статистика
        self.stats = {
            'processed_chats': 0,
            'sent_responses': 0,
            'failed_responses': 0,
            'transferred_to_human': 0,
            'initiative_messages': 0
        }

    # ❗ НОВОЕ: Методы для работы с виртуальным временем
    def get_current_time(self) -> datetime:
        """Получить текущее время (реальное или виртуальное для тестов)"""
        if settings.test_mode:
            # В тест режиме время ускорено
            multiplier = settings.get_time_multiplier()
            real_elapsed = (datetime.utcnow() - self.test_start_time).total_seconds()
            virtual_elapsed = real_elapsed * multiplier
            return self.test_start_time + timedelta(seconds=virtual_elapsed)
        else:
            return datetime.utcnow()

    def get_moscow_time(self) -> datetime:
        """Получить московское время (реальное или виртуальное)"""
        current = self.get_current_time()
        return current + timedelta(hours=3)  # UTC+3

    def log_test_info(self, message: str):
        """Логирование для тестирования"""
        if settings.test_mode or settings.dev_mode:
            moscow_time = self.get_moscow_time()
            logger.info(f"🧪 TEST [{moscow_time.strftime('%H:%M:%S')}]: {message}")

    async def start(self) -> bool:
        """Запуск мониторинга с тест режимом"""
        try:
            # Подключаемся к Telegram
            if not await self.telegram_client.initialize():
                logger.error("Не удалось инициализировать Telegram клиент")
                return False

            if not await self.telegram_client.connect():
                logger.error("Не удалось подключиться к Telegram")
                return False

            # Инициализируем состояние
            await self._init_last_processed()
            await self._load_stopped_chats()

            # ❗ НОВОЕ: Инициализируем тест режим
            if settings.test_mode:
                self.test_start_time = datetime.utcnow()
                logger.critical("🧪 ЗАПУЩЕН TEST_MODE - время ускорено в 3600 раз!")
                logger.critical("🧪 1 час = 1 секунда, весь пайплайн за 5-10 минут!")
            elif settings.dev_mode:
                logger.warning("⚡ ЗАПУЩЕН DEV_MODE - время ускорено в 60 раз!")

            self.is_monitoring = True
            logger.info("🚀 Мониторинг запущен")
            logger.info(f"👤 Персонаж: {self.response_generator.character.name}")

            # Основной цикл
            await self._simple_monitoring_loop()

            return True

        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
        except Exception as e:
            logger.error(f"Ошибка запуска мониторинга: {e}")
        finally:
            if self.telegram_client:
                await self.telegram_client.stop_monitoring()
            logger.info("👋 Мониторинг остановлен")

        return False

    async def stop(self):
        """Остановка мониторинга"""
        self.is_monitoring = False
        await self.telegram_client.stop_monitoring()
        logger.info("Мониторинг остановлен")

    async def _load_stopped_chats(self):
        """Загружаем чаты переданные человеку"""
        try:
            from ..database.models import DialogueStage
            with db_manager.get_session() as session:
                stopped_stages = session.query(DialogueStage).filter(
                    DialogueStage.dialogue_stopped == True
                ).all()
                
                for stage in stopped_stages:
                    self.stopped_chats.add(stage.chat_id)
                    
                logger.info(f"📵 Загружено {len(self.stopped_chats)} остановленных чатов")
                
        except Exception as e:
            logger.error(f"Ошибка загрузки остановленных чатов: {e}")

    async def _init_last_processed(self):
        """Простая инициализация последних сообщений"""
        try:
            active_chats = db_manager.get_active_chats()

            for chat in active_chats:
                last_id = db_manager.get_last_processed_message_id(chat.id)
                self.last_processed_message_ids[chat.id] = last_id

            logger.info(f"Инициализировано {len(active_chats)} активных чатов")

        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}")

    async def _simple_monitoring_loop(self):
        """Основной цикл мониторинга с поддержкой тест режима"""
        interval = settings.monitor_interval
        if settings.test_mode:
            interval = 2  # В тест режиме проверяем каждые 2 секунды
        elif settings.dev_mode:
            interval = 5  # В дев режиме каждые 5 секунд
            
        logger.info(f"Цикл мониторинга с интервалом {interval} секунд")

        while self.is_monitoring:
            try:
                # Проверяем подключение
                if not await self.telegram_client.ensure_connection():
                    logger.error("Нет подключения, ждем...")
                    await asyncio.sleep(interval * 2)
                    continue

                # ❗ НОВОЕ: Проверяем инициативные сообщения (с учетом тест времени)
                await self._check_initiative_messages_fast()

                # Отправляем готовые ответы
                await self._send_ready_responses()

                # Проверяем новые сообщения
                await self._check_new_messages()

                # Пауза
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(interval)

    # ❗ НОВОЕ: Ускоренная проверка инициативных сообщений
    async def _check_initiative_messages_fast(self):
        """Проверка инициативных сообщений с поддержкой тест режима"""
        try:
            current_time = self.get_current_time()
            moscow_time = self.get_moscow_time()
            current_hour = moscow_time.hour
            
            active_chats = db_manager.get_active_chats()
            
            for chat in active_chats:
                # Пропускаем остановленные чаты
                if chat.id in self.stopped_chats:
                    continue
                    
                # Проверяем разные типы инициативных сообщений
                await self._check_morning_greeting_fast(chat, current_hour, moscow_time)
                await self._check_evening_greeting_fast(chat, current_hour, moscow_time)
                await self._check_are_you_busy_fast(chat, current_time)
                
        except Exception as e:
            logger.error(f"Ошибка проверки инициативных сообщений: {e}")

    async def _check_morning_greeting_fast(self, chat: Chat, current_hour: int, moscow_time: datetime):
        """Ускоренная проверка утренних приветствий"""
        try:
            # ❗ НОВОЕ: Проверяем время с учетом тест режима
            if not settings.is_test_morning_time(current_hour):
                return
                
            self.log_test_info(f"Проверяем утреннее приветствие для чата {chat.id} (час: {current_hour})")
                
            # Проверяем не отправляли ли уже сегодня
            if settings.test_mode:
                # В тест режиме "день" = последние 60 виртуальных секунд
                today_start = moscow_time - timedelta(seconds=60)
            else:
                today_start = moscow_time.replace(hour=0, minute=0, second=0, microsecond=0)
            
            recent_messages = db_manager.get_chat_messages(chat.id, limit=20)
            
            # Проверяем есть ли сообщения за "сегодня"
            today_messages = [
                msg for msg in recent_messages 
                if msg.created_at >= today_start - timedelta(hours=3)  # Учитываем UTC
            ]
            
            if not today_messages:
                # Никто не писал сегодня - отправляем утреннее приветствие
                greetings = [
                    "Доброе утро! Как дела?",
                    "Привет! Как спалось?", 
                    "Доброе утро) Планы на день какие?",
                    "Утро! Как настроение?"
                ]
                
                message = random.choice(greetings)
                await self._send_initiative_message_fast(chat, message, "morning_greeting")
                self.log_test_info(f"Отправляем утреннее приветствие в чат {chat.id}")
                return
                
            # Проверяем не писала ли она первой сегодня
            first_today = today_messages[0] if today_messages else None
            if first_today and not first_today.is_from_ai:
                # Она писала первой - не навязываемся
                return
                
            # Проверяем не отправляли ли мы уже утреннее приветствие
            ai_messages_today = [msg for msg in today_messages if msg.is_from_ai]
            morning_greetings = [
                msg for msg in ai_messages_today 
                if any(word in (msg.text or "").lower() for word in ["утро", "доброе", "привет"])
            ]
            
            if not morning_greetings:
                greetings = [
                    "Доброе утро! Как дела?",
                    "Привет! Как дела у тебя?",
                    "Утро) Как спалось?"
                ]
                
                message = random.choice(greetings)
                await self._send_initiative_message_fast(chat, message, "morning_greeting")
                self.log_test_info(f"Отправляем утреннее приветствие в чат {chat.id}")
                
        except Exception as e:
            logger.error(f"Ошибка утреннего приветствия для чата {chat.id}: {e}")

    async def _check_evening_greeting_fast(self, chat: Chat, current_hour: int, moscow_time: datetime):
        """Ускоренная проверка вечерних приветствий"""
        try:
            # ❗ НОВОЕ: Проверяем время с учетом тест режима
            if not settings.is_test_evening_time(current_hour):
                return
                
            self.log_test_info(f"Проверяем вечернее приветствие для чата {chat.id} (час: {current_hour})")
                
            # Проверяем было ли активное общение сегодня
            if settings.test_mode:
                today_start = moscow_time - timedelta(seconds=60)  # Последние 60 виртуальных секунд
            else:
                today_start = moscow_time.replace(hour=0, minute=0, second=0, microsecond=0)
            
            recent_messages = db_manager.get_chat_messages(chat.id, limit=20)
            today_messages = [
                msg for msg in recent_messages 
                if msg.created_at >= today_start - timedelta(hours=3)
            ]
            
            min_messages = 2 if settings.test_mode else 3
            if len(today_messages) < min_messages:
                return  # Не было активного общения
                
            # Проверяем не отправляли ли уже вечернее приветствие
            ai_messages_today = [msg for msg in today_messages if msg.is_from_ai]
            evening_greetings = [
                msg for msg in ai_messages_today 
                if any(word in (msg.text or "").lower() for word in ["спокойной", "ночи", "сладких"])
            ]
            
            if not evening_greetings:
                # Проверяем что последнее сообщение не от нас недавно
                last_message = recent_messages[-1] if recent_messages else None
                if last_message and last_message.is_from_ai:
                    time_delays = settings.get_time_delays()
                    min_gap = time_delays['initiative_min_delay']
                    
                    time_since_last = (self.get_current_time() - last_message.created_at).total_seconds()
                    if time_since_last < min_gap:
                        return
                
                greetings = [
                    "Спокойной ночи) Сладких снов!",
                    "Доброй ночи! До завтра)",
                    "Ночи) Отдыхай хорошо!"
                ]
                
                message = random.choice(greetings)
                await self._send_initiative_message_fast(chat, message, "evening_greeting")
                self.log_test_info(f"Отправляем вечернее приветствие в чат {chat.id}")
                
        except Exception as e:
            logger.error(f"Ошибка вечернего приветствия для чата {chat.id}: {e}")

    async def _check_are_you_busy_fast(self, chat: Chat, current_time: datetime):
        """Ускоренная проверка 'Занята?'"""
        try:
            recent_messages = db_manager.get_chat_messages(chat.id, limit=10)
            if not recent_messages:
                return
                
            last_message = recent_messages[-1]
            
            # Проверяем что последнее сообщение от нас с вопросом
            if not last_message.is_from_ai or not last_message.text:
                return
                
            if '?' not in last_message.text:
                return  # Не был вопрос
                
            # ❗ НОВОЕ: Получаем ускоренную задержку для тестов
            time_delays = settings.get_time_delays()
            busy_delay = time_delays['are_you_busy_delay']
            
            # Проверяем прошло ли нужное время
            time_since = (current_time - last_message.created_at).total_seconds()
            if time_since < busy_delay:
                return
                
            self.log_test_info(f"Проверяем 'Занята?' для чата {chat.id} (прошло {time_since:.1f}с, нужно {busy_delay}с)")
                
            # Проверяем что она не отвечала после нашего вопроса
            messages_after = [
                msg for msg in recent_messages 
                if msg.created_at > last_message.created_at and not msg.is_from_ai
            ]
            
            if messages_after:
                return  # Она уже отвечала
                
            # Проверяем не спрашивали ли уже "Занята?"
            recent_ai_messages = [msg for msg in recent_messages[-5:] if msg.is_from_ai]
            busy_questions = [
                msg for msg in recent_ai_messages 
                if any(word in (msg.text or "").lower() for word in ["занята", "busy", "свободна"])
            ]
            
            if busy_questions:
                return  # Уже спрашивали
                
            # Отправляем "Занята?"
            messages = ["Занята?", "Свободна?", "Как дела?"]
            message = random.choice(messages)
            await self._send_initiative_message_fast(chat, message, "are_you_busy")
            self.log_test_info(f"Отправляем 'Занята?' в чат {chat.id}")
            
        except Exception as e:
            logger.error(f"Ошибка проверки 'Занята?' для чата {chat.id}: {e}")

    async def _send_initiative_message_fast(self, chat: Chat, message: str, message_type: str):
        """Ускоренная отправка инициативного сообщения"""
        try:
            # ❗ НОВОЕ: Ускоренные задержки для тестов
            time_delays = settings.get_time_delays()
            min_delay = time_delays['initiative_min_delay']
            max_delay = time_delays['initiative_max_delay']
            
            delay = random.randint(min_delay, max_delay)
            send_time = self.get_current_time() + timedelta(seconds=delay)
            
            self.response_queue.append({
                'chat_id': chat.id,
                'telegram_user_id': chat.telegram_user_id,
                'message_text': message,
                'send_time': send_time,
                'message_batch': None,  # Инициативное сообщение
                'initiative_type': message_type
            })
            
            self.log_test_info(f"Инициативное сообщение ({message_type}) запланировано для чата {chat.id} через {delay}с: {message}")
            
        except Exception as e:
            logger.error(f"Ошибка планирования инициативного сообщения: {e}")

    # Остальные методы остаются без изменений, но используют self.get_current_time() вместо datetime.utcnow()

    async def _check_new_messages(self):
        """Простая проверка новых сообщений"""
        try:
            active_chats = db_manager.get_active_chats()

            for chat in active_chats:
                # Пропускаем остановленные чаты
                if chat.id in self.stopped_chats:
                    continue
                    
                await self._process_chat_simple(chat)

            self.stats['processed_chats'] = len([c for c in active_chats if c.id not in self.stopped_chats])

        except Exception as e:
            logger.error(f"Ошибка проверки сообщений: {e}")

    async def _process_chat_simple(self, chat):
        """Простая обработка чата с защитой от дублей"""
        try:
            chat_id = chat.id
            last_processed_id = self.last_processed_message_ids.get(chat_id, 0)

            # Проверяем остановлен ли чат
            if chat_id in self.stopped_chats:
                return

            # Получаем новые сообщения
            message_batch = db_manager.get_unprocessed_user_messages(
                chat_id=chat_id,
                last_processed_id=last_processed_id,
                time_window_seconds=60
            )

            if not message_batch.messages:
                return

            # ПРОВЕРЯЕМ НЕТ ЛИ УЖЕ ОТВЕТА В ОЧЕРЕДИ
            pending_response = None
            for i, response in enumerate(self.response_queue):
                if response['chat_id'] == chat_id:
                    pending_response = response
                    pending_index = i
                    break

            if pending_response:
                # ЕСЛИ ЕСТЬ НОВЫЕ СООБЩЕНИЯ - ОБНОВЛЯЕМ ОТВЕТ
                self.log_test_info(f"Обновляем ответ для чата {chat_id} с учетом новых сообщений")

                # Удаляем старый ответ из очереди
                self.response_queue.pop(pending_index)

                # Генерируем новый ответ с учетом ВСЕХ сообщений
                response_text = await self.response_generator.generate_response_for_batch(
                    chat_id, message_batch
                )

                # Проверяем стоп-сигнал
                if response_text and self._is_stop_signal(response_text):
                    await self._transfer_to_human(chat_id, message_batch, response_text)
                    return

                if response_text:
                    # Рассчитываем новую задержку (меньше, так как уже ждали)
                    delay = self._calculate_natural_delay_fast(message_batch, chat_id) // 2
                    send_time = self.get_current_time() + timedelta(seconds=delay)

                    # Добавляем обновленный ответ
                    self.response_queue.append({
                        'chat_id': chat_id,
                        'telegram_user_id': chat.telegram_user_id,
                        'message_text': response_text,
                        'send_time': send_time,
                        'message_batch': message_batch
                    })

                    self.log_test_info(f"Ответ обновлен для чата {chat_id}, новая задержка: {delay}с")

                # Обновляем ID последнего обработанного
                self.last_processed_message_ids[chat_id] = message_batch.messages[-1].id
                return

            # ПРОВЕРЯЕМ НЕ ОТВЕЧАЛИ ЛИ МЫ НЕДАВНО
            recent_messages = db_manager.get_chat_messages(chat_id, limit=5)
            if recent_messages and recent_messages[-1].is_from_ai:
                time_since_our_response = (self.get_current_time() - recent_messages[-1].created_at).total_seconds()
                min_gap = 30 if settings.test_mode else 300  # 30 сек в тесте, 5 мин в проде
                if time_since_our_response < min_gap:
                    return

            self.log_test_info(f"Новые сообщения в чате {chat_id}: {len(message_batch.messages)}")

            # Проверяем нужно ли отвечать
            if not self.response_generator.should_respond(chat_id, message_batch):
                return

            # Генерируем ответ
            response_text = await self.response_generator.generate_response_for_batch(
                chat_id, message_batch
            )

            if not response_text:
                logger.warning(f"Не удалось сгенерировать ответ для чата {chat_id}")
                return

            # Проверяем стоп-сигнал
            if self._is_stop_signal(response_text):
                await self._transfer_to_human(chat_id, message_batch, response_text)
                return

            # Рассчитываем естественную задержку
            delay = self._calculate_natural_delay_fast(message_batch, chat_id)
            send_time = self.get_current_time() + timedelta(seconds=delay)

            # Добавляем в очередь
            self.response_queue.append({
                'chat_id': chat_id,
                'telegram_user_id': chat.telegram_user_id,
                'message_text': response_text,
                'send_time': send_time,
                'message_batch': message_batch
            })

            # Обновляем ID последнего обработанного
            self.last_processed_message_ids[chat_id] = message_batch.messages[-1].id

            self.log_test_info(f"Ответ запланирован для чата {chat_id} через {delay}с")

        except Exception as e:
            logger.error(f"Ошибка обработки чата {chat.id}: {e}")

    def _calculate_natural_delay_fast(self, message_batch: MessageBatch, chat_id: int) -> int:
        """Ускоренный расчет естественной задержки"""
        if settings.test_mode:
            # В тест режиме базовая задержка 1-5 секунд
            return random.randint(1, 5)
        elif settings.dev_mode:
            # В дев режиме 5-15 секунд
            return random.randint(5, 15)
        else:
            # Обычная логика
            base_delay = random.randint(8, 25)
            
            # Корректировки остаются теми же
            current_hour = datetime.now().hour
            if 0 <= current_hour < 7:
                base_delay *= 2
            elif 9 <= current_hour < 18:
                base_delay *= 0.8
            elif 22 <= current_hour < 24:
                base_delay *= 1.5

            message_length = len(message_batch.total_text)
            if message_length > 100:
                base_delay += random.randint(5, 15)

            if len(message_batch.messages) > 1:
                base_delay += len(message_batch.messages) * 3

            try:
                facts = db_manager.get_person_facts(chat_id)
                fact_count = len(facts)

                if fact_count >= 3:
                    base_delay *= 0.7
                elif fact_count == 0:
                    base_delay *= 1.3
            except Exception:
                pass

            randomness = random.uniform(0.7, 1.3)
            final_delay = int(base_delay * randomness)

            return max(5, min(final_delay, 180))

    # Проверка стоп-сигналов
    def _is_stop_signal(self, response_text: str) -> bool:
        """Проверяем является ли ответ стоп-сигналом"""
        if not response_text:
            return False
            
        response_lower = response_text.lower()
        
        stop_phrases = [
            "окей, давай! сейчас разберусь",
            "давай созвонимся",
            "наберу тебе",
            "позвоню тебе",
            "можем созвониться",
            "уведомляем заказчика"
        ]
        
        return any(phrase in response_lower for phrase in stop_phrases)

    # Передача человеку
    async def _transfer_to_human(self, chat_id: int, message_batch: MessageBatch, response_text: str):
        """Передаем чат человеку и останавливаем ИИ"""
        try:
            # Отправляем финальный ответ
            chat = db_manager.get_chat_by_id(chat_id)
            if chat:
                success = await self.telegram_client.send_message(
                    chat.telegram_user_id, response_text
                )
                
                if success:
                    # Сохраняем финальное сообщение
                    db_manager.add_message(
                        chat_id=chat_id,
                        text=response_text,
                        is_from_ai=True
                    )
            
            # Останавливаем чат
            self.stopped_chats.add(chat_id)
            
            # Отмечаем в БД
            db_manager.mark_dialogue_success(chat_id, "wants_call")
            
            # Уведомляем оператора
            await self._notify_operator(chat_id, message_batch, response_text)
            
            self.stats['transferred_to_human'] += 1
            logger.critical(f"🎯 ЧАТ {chat_id} ПЕРЕДАН ЧЕЛОВЕКУ! Стоп-сигнал: {response_text[:50]}...")
            
        except Exception as e:
            logger.error(f"Ошибка передачи чата {chat_id} человеку: {e}")

    async def _notify_operator(self, chat_id: int, message_batch: MessageBatch, final_response: str):
        """Уведомляем оператора о передаче чата"""
        try:
            chat = db_manager.get_chat_by_id(chat_id)
            if not chat:
                return
                
            # Получаем контекст диалога
            context = db_manager.get_recent_conversation_context(chat_id, limit=20)
            facts = db_manager.get_person_facts(chat_id)
            
            # Формируем уведомление
            notification = f"""🎯 СТОП-СИГНАЛ! Чат передан оператору

👤 Собеседница: {chat.first_name or 'Без имени'} (@{chat.username or 'нет username'})
📱 Telegram ID: {chat.telegram_user_id}
💬 Chat ID: {chat_id}

🔥 Стоп-сигнал: {final_response}

📝 Факты о ней:"""
            
            for fact in facts[:5]:  # Топ 5 фактов
                notification += f"\n   • {fact.fact_type}: {fact.fact_value}"
                
            notification += f"\n\n📜 Последние сообщения:\n{context[-500:]}"  # Последние 500 символов
            
            # ID оператора (нужно настроить в .env)
            operator_id = getattr(settings, 'operator_telegram_id', None)
            
            if operator_id:
                await self.telegram_client.send_message(operator_id, notification)
                logger.info(f"📢 Уведомление оператору отправлено")
            else:
                # Пишем в лог если нет ID оператора
                logger.critical(f"📢 УВЕДОМЛЕНИЕ ОПЕРАТОРУ:\n{notification}")
                
        except Exception as e:
            logger.error(f"Ошибка уведомления оператора: {e}")

    async def _send_ready_responses(self):
        """Отправка готовых ответов с отладкой"""
        current_time = self.get_current_time()  # ❗ НОВОЕ: используем виртуальное время

        ready_responses = []
        remaining_responses = []

        for response in self.response_queue:
            if response['send_time'] <= current_time:
                ready_responses.append(response)
            else:
                remaining_responses.append(response)

        self.response_queue = remaining_responses

        # Отправляем готовые
        for response in ready_responses:
            self.log_test_info(f"Отправляем готовый ответ в чат {response['chat_id']}")
            await self._send_response_naturally(response)

    async def _send_response_naturally(self, response: Dict):
        """Естественная отправка ответа"""
        try:
            chat_id = response['chat_id']
            telegram_user_id = response['telegram_user_id']
            message_text = response['message_text']
            message_batch = response['message_batch']
            initiative_type = response.get('initiative_type')

            # Проверяем подключение
            if not await self.telegram_client.ensure_connection():
                logger.error(f"Нет подключения для отправки в чат {chat_id}")
                self.stats['failed_responses'] += 1
                return

            # Отправляем (с прочтением и typing внутри)
            success = await self.telegram_client.send_message(
                telegram_user_id, message_text
            )

            if success:
                # Сохраняем в БД
                db_manager.add_message(
                    chat_id=chat_id,
                    text=message_text,
                    is_from_ai=True
                )

                # Отмечаем как обработанные если не инициативное
                if message_batch:
                    db_manager.mark_messages_as_processed(message_batch)

                if initiative_type:
                    self.stats['initiative_messages'] += 1
                    self.log_test_info(f"Инициативное сообщение ({initiative_type}) отправлено в чат {chat_id}")
                else:
                    self.stats['sent_responses'] += 1
                    self.log_test_info(f"Ответ отправлен в чат {chat_id}")
            else:
                self.stats['failed_responses'] += 1
                logger.warning(f"❌ Не удалось отправить в чат {chat_id}")

        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}")
            self.stats['failed_responses'] += 1

    # Остальные методы без изменений...
    async def send_manual_message(self, user_id: int, message: str) -> bool:
        """Ручная отправка сообщения"""
        try:
            if not await self.telegram_client.ensure_connection():
                return False

            success = await self.telegram_client.send_message(user_id, message)

            if success:
                # Сохраняем в БД
                chat = db_manager.get_or_create_chat(telegram_user_id=user_id)
                db_manager.add_message(
                    chat_id=chat.id,
                    text=message,
                    is_from_ai=True
                )

                logger.info(f"✅ Ручное сообщение отправлено {user_id}")

            return success

        except Exception as e:
            logger.error(f"Ошибка ручной отправки: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Получить статус мониторинга"""
        telegram_status = self.telegram_client.get_status()

        status = {
            'monitoring': self.is_monitoring,
            'telegram_connected': telegram_status['connected'],
            'response_queue_size': len(self.response_queue),
            'active_chats': len(db_manager.get_active_chats()),
            'stopped_chats': len(self.stopped_chats),
            'stats': self.stats.copy(),
            'telegram_stats': telegram_status.get('stats', {})
        }

        # ❗ НОВОЕ: Добавляем информацию о тест режиме
        if settings.test_mode:
            status['test_mode'] = True
            status['virtual_time'] = self.get_moscow_time().strftime('%H:%M:%S')
            status['time_multiplier'] = settings.get_time_multiplier()
        elif settings.dev_mode:
            status['dev_mode'] = True
            status['time_multiplier'] = settings.get_time_multiplier()

        return status

    async def get_dialogs(self) -> List[Dict[str, Any]]:
        """Получить список диалогов"""
        if not await self.telegram_client.ensure_connection():
            return []

        return await self.telegram_client.get_dialogs()

    def get_queue_info(self) -> List[Dict[str, Any]]:
        """Информация об очереди ответов"""
        queue_info = []
        current_time = self.get_current_time()  # ❗ НОВОЕ: виртуальное время

        for response in sorted(self.response_queue, key=lambda x: x['send_time']):
            time_to_send = (response['send_time'] - current_time).total_seconds()
            
            delay_reason = 'natural_timing'
            if response.get('initiative_type'):
                delay_reason = f"initiative_{response['initiative_type']}"
                
            queue_info.append({
                'chat_id': response['chat_id'],
                'message_preview': response['message_text'][:50] + "...",
                'time_to_send_seconds': max(0, time_to_send),
                'delay_reason': delay_reason
            })

        return queue_info