"""
Упрощенный мониторинг сообщений - фокус на естественности
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
    """Простой естественный мониторинг сообщений"""

    def __init__(self):
        self.telegram_client = TelegramAIClient()
        self.response_generator = ResponseGenerator()
        self.is_monitoring = False

        # Простое отслеживание последних сообщений
        self.last_processed_message_ids: Dict[int, int] = {}

        # Простая очередь ответов
        self.response_queue: List[Dict] = []

        # Базовая статистика
        self.stats = {
            'processed_chats': 0,
            'sent_responses': 0,
            'failed_responses': 0
        }

    async def start(self) -> bool:
        """Запуск простого мониторинга"""
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

            self.is_monitoring = True
            logger.info("🚀 Простой мониторинг запущен")
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
        """Простой цикл мониторинга"""
        logger.info(f"Начат мониторинг с интервалом {settings.monitor_interval} секунд")

        while self.is_monitoring:
            try:
                # Проверяем подключение
                if not await self.telegram_client.ensure_connection():
                    logger.error("Нет подключения, ждем...")
                    await asyncio.sleep(settings.monitor_interval * 2)
                    continue

                # Отправляем готовые ответы
                await self._send_ready_responses()

                # Проверяем новые сообщения
                await self._check_new_messages()

                # Пауза
                await asyncio.sleep(settings.monitor_interval)

            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(settings.monitor_interval)

    async def _check_new_messages(self):
        """Простая проверка новых сообщений"""
        try:
            active_chats = db_manager.get_active_chats()

            for chat in active_chats:
                await self._process_chat_simple(chat)

            self.stats['processed_chats'] = len(active_chats)

        except Exception as e:
            logger.error(f"Ошибка проверки сообщений: {e}")

    async def _process_chat_simple(self, chat):
        """Простая обработка чата с защитой от дублей"""
        try:
            chat_id = chat.id
            last_processed_id = self.last_processed_message_ids.get(chat_id, 0)

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
                logger.info(f"📝 Обновляем ответ для чата {chat_id} с учетом новых сообщений")

                # Удаляем старый ответ из очереди
                self.response_queue.pop(pending_index)

                # Генерируем новый ответ с учетом ВСЕХ сообщений
                response_text = await self.response_generator.generate_response_for_batch(
                    chat_id, message_batch
                )

                if response_text:
                    # Рассчитываем новую задержку (меньше, так как уже ждали)
                    delay = self._calculate_natural_delay(message_batch, chat_id) // 2  # Вдвое меньше
                    send_time = datetime.utcnow() + timedelta(seconds=delay)

                    # Добавляем обновленный ответ
                    self.response_queue.append({
                        'chat_id': chat_id,
                        'telegram_user_id': chat.telegram_user_id,
                        'message_text': response_text,
                        'send_time': send_time,
                        'message_batch': message_batch
                    })

                    logger.info(f"🔄 Ответ обновлен для чата {chat_id}, новая задержка: {delay}с")

                # Обновляем ID последнего обработанного
                self.last_processed_message_ids[chat_id] = message_batch.messages[-1].id
                return

            # ПРОВЕРЯЕМ НЕ ОТВЕЧАЛИ ЛИ МЫ НЕДАВНО
            recent_messages = db_manager.get_chat_messages(chat_id, limit=5)
            if recent_messages and recent_messages[-1].is_from_ai:
                time_since_our_response = (datetime.utcnow() - recent_messages[-1].created_at).total_seconds()
                if time_since_our_response < 300:  # 5 минут
                    logger.debug(f"Недавно отвечали в чат {chat_id}, ждем")
                    return

            logger.info(f"📬 Новые сообщения в чате {chat_id}: {len(message_batch.messages)}")

            # Проверяем нужно ли отвечать
            if not self.response_generator.should_respond(chat_id, message_batch):
                return

            # Остальная логика без изменений...
            response_text = await self.response_generator.generate_response_for_batch(
                chat_id, message_batch
            )

            if not response_text:
                logger.warning(f"Не удалось сгенерировать ответ для чата {chat_id}")
                return

            # Рассчитываем естественную задержку
            delay = self._calculate_natural_delay(message_batch, chat_id)
            send_time = datetime.utcnow() + timedelta(seconds=delay)

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

            logger.info(f"📅 Ответ запланирован для чата {chat_id} через {delay}с")

        except Exception as e:
            logger.error(f"Ошибка обработки чата {chat.id}: {e}")

    def _calculate_natural_delay(self, message_batch: MessageBatch, chat_id: int) -> int:
        """Расчет естественной задержки с учетом фактов"""

        # Базовая задержка
        base_delay = random.randint(8, 25)

        # Корректировка по времени суток
        current_hour = datetime.now().hour
        if 0 <= current_hour < 7:      # Ночь - дольше
            base_delay *= 2
        elif 9 <= current_hour < 18:   # Рабочий день - быстрее
            base_delay *= 0.8
        elif 22 <= current_hour < 24:  # Поздний вечер - дольше
            base_delay *= 1.5

        # Корректировка по длине сообщения
        message_length = len(message_batch.total_text)
        if message_length > 100:
            base_delay += random.randint(5, 15)

        # Корректировка по количеству сообщений
        if len(message_batch.messages) > 1:
            base_delay += len(message_batch.messages) * 3

        # Корректировка по этапу отношений (простая логика)
        try:
            facts = db_manager.get_person_facts(chat_id)
            fact_count = len(facts)

            if fact_count >= 3:  # Знаем много о собеседнице - быстрее отвечаем
                base_delay *= 0.7
            elif fact_count == 0:  # Только знакомимся - медленнее
                base_delay *= 1.3
        except Exception:
            pass

        # Случайность для естественности
        randomness = random.uniform(0.7, 1.3)
        final_delay = int(base_delay * randomness)

        return max(5, min(final_delay, 180))  # От 5 секунд до 3 минут

    async def _send_ready_responses(self):
        """Отправка готовых ответов с отладкой"""
        current_time = datetime.utcnow()

        if self.response_queue:
            logger.debug(
                f"🕐 Проверяем очередь ({len(self.response_queue)} ответов). Текущее время: {current_time.strftime('%H:%M:%S')}")
            for i, response in enumerate(self.response_queue):
                time_diff = (response['send_time'] - current_time).total_seconds()
                logger.debug(
                    f"   {i + 1}. Чат {response['chat_id']}: {'готов' if time_diff <= 0 else f'через {time_diff:.0f}с'}")

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
            logger.info(f"📤 Отправляем готовый ответ в чат {response['chat_id']}")
            await self._send_response_naturally(response)

    async def _send_response_naturally(self, response: Dict):
        """Естественная отправка ответа"""
        try:
            chat_id = response['chat_id']
            telegram_user_id = response['telegram_user_id']
            message_text = response['message_text']
            message_batch = response['message_batch']

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

                # Отмечаем как обработанные
                db_manager.mark_messages_as_processed(message_batch)

                self.stats['sent_responses'] += 1
                logger.info(f"✅ Ответ отправлен в чат {chat_id}")
            else:
                self.stats['failed_responses'] += 1
                logger.warning(f"❌ Не удалось отправить ответ в чат {chat_id}")

        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}")
            self.stats['failed_responses'] += 1

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

        return {
            'monitoring': self.is_monitoring,
            'telegram_connected': telegram_status['connected'],
            'response_queue_size': len(self.response_queue),
            'active_chats': len(db_manager.get_active_chats()),
            'stats': self.stats.copy(),
            'telegram_stats': telegram_status.get('stats', {})
        }

    async def get_dialogs(self) -> List[Dict[str, Any]]:
        """Получить список диалогов"""
        if not await self.telegram_client.ensure_connection():
            return []

        return await self.telegram_client.get_dialogs()

    def get_queue_info(self) -> List[Dict[str, Any]]:
        """Информация об очереди ответов"""
        queue_info = []
        current_time = datetime.utcnow()

        for response in sorted(self.response_queue, key=lambda x: x['send_time']):
            time_to_send = (response['send_time'] - current_time).total_seconds()
            queue_info.append({
                'chat_id': response['chat_id'],
                'message_preview': response['message_text'][:50] + "...",
                'time_to_send_seconds': max(0, time_to_send),
                'delay_reason': 'natural_timing'
            })

        return queue_info