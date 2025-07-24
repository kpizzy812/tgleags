"""
Мониторинг и обработка сообщений (Кардинально улучшенная версия)
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from loguru import logger

from ..config.settings import settings
from ..database.database import db_manager, MessageBatch
from ..database.models import Chat
from ..utils.helpers import get_random_delay, get_smart_delay
from .telegram_client import TelegramAIClient
from .response_generator import ResponseGenerator


class MessageMonitor:
    """Умный мониторинг и автоматическая обработка сообщений"""
    
    def __init__(self):
        self.telegram_client = TelegramAIClient()
        self.response_generator = ResponseGenerator()
        self.is_monitoring = False
        
        # Отслеживание обработанных сообщений для каждого чата
        self.last_processed_message_ids: Dict[int, int] = {}  # chat_id -> last_message_id
        
        # Очередь ответов с умным планированием
        self.response_queue: List[Dict] = []
        
        # Статистика для мониторинга
        self.stats = {
            'processed_chats': 0,
            'processed_message_batches': 0,
            'sent_responses': 0,
            'failed_responses': 0,
            'reconnections': 0
        }
        
        # Настройки группировки сообщений
        self.message_grouping_window = 30  # секунд
        self.max_concurrent_chats = settings.max_concurrent_chats
        
    async def start(self) -> bool:
        """Запуск умного мониторинга"""
        try:
            # Инициализируем и подключаем Telegram клиент
            if not await self.telegram_client.initialize():
                logger.error("Не удалось инициализировать Telegram клиент")
                return False
            
            if not await self.telegram_client.connect():
                logger.error("Не удалось подключиться к Telegram")
                return False
            
            # Инициализируем состояние обработанных сообщений
            await self._initialize_processed_state()
            
            self.is_monitoring = True
            logger.info("🚀 Умный мониторинг сообщений запущен")
            logger.info(f"📱 Персонаж: {self.response_generator.character.name}")
            logger.info(f"🔄 Интервал мониторинга: {settings.monitor_interval} сек")
            logger.info(f"📦 Окно группировки сообщений: {self.message_grouping_window} сек")
            logger.info(f"👥 Максимум чатов одновременно: {self.max_concurrent_chats}")
            
            # Запускаем основной цикл мониторинга
            await self._monitoring_loop()
            
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
    
    async def _initialize_processed_state(self):
        """Инициализация состояния последних обработанных сообщений"""
        try:
            active_chats = db_manager.get_active_chats()
            
            for chat in active_chats:
                last_id = db_manager.get_last_processed_message_id(chat.id)
                self.last_processed_message_ids[chat.id] = last_id
                
            logger.info(f"Инициализировано состояние для {len(active_chats)} чатов")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации состояния: {e}")
    
    async def _monitoring_loop(self):
        """Основной цикл мониторинга с умной обработкой"""
        logger.info(f"Начат умный мониторинг с интервалом {settings.monitor_interval} секунд")
        
        while self.is_monitoring:
            try:
                # Убеждаемся что клиент подключен
                if not await self.telegram_client.ensure_connection():
                    logger.error("Не удалось обеспечить подключение, ждем...")
                    await asyncio.sleep(settings.monitor_interval * 2)
                    self.stats['reconnections'] += 1
                    continue
                
                # Обрабатываем очередь ответов
                await self._process_response_queue()
                
                # Проверяем новые сообщения
                await self._check_new_messages()
                
                # Логируем статистику
                self._log_stats()
                
                # Пауза перед следующей итерацией
                await asyncio.sleep(settings.monitor_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(settings.monitor_interval)
    
    async def _check_new_messages(self):
        """Проверка новых сообщений во всех активных чатах"""
        try:
            # Получаем активные чаты из БД
            active_chats = db_manager.get_active_chats()
            
            # Обрабатываем чаты пакетами для избежания перегрузки
            for i in range(0, len(active_chats), self.max_concurrent_chats):
                batch_chats = active_chats[i:i + self.max_concurrent_chats]
                
                # Обрабатываем пакет чатов параллельно
                tasks = [self._process_chat_smart(chat) for chat in batch_chats]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Небольшая пауза между пакетами
                if i + self.max_concurrent_chats < len(active_chats):
                    await asyncio.sleep(1)
            
            self.stats['processed_chats'] = len(active_chats)
            
        except Exception as e:
            logger.error(f"Ошибка проверки новых сообщений: {e}")

    async def _process_chat_smart(self, chat):
        """Умная обработка отдельного чата с новой архитектурой анализа"""
        try:
            chat_id = chat.id
            last_processed_id = self.last_processed_message_ids.get(chat_id, 0)

            # Получаем пакет необработанных сообщений
            message_batch = db_manager.get_unprocessed_user_messages(
                chat_id=chat_id,
                last_processed_id=last_processed_id,
                time_window_seconds=self.message_grouping_window
            )

            # Если нет новых сообщений - пропускаем
            if not message_batch.messages:
                return

            logger.info(f"📬 Новый пакет в чате {chat_id}: {message_batch.get_context_summary()}")

            # НОВАЯ ЛОГИКА: Используем улучшенный ResponseGenerator
            response_text = await self.response_generator.generate_response_for_batch(
                chat_id,
                message_batch
            )

            if not response_text:
                logger.warning(f"Не удалось сгенерировать ответ для чата {chat_id}")
                return

            # Проверяем не является ли это сигналом завершения диалога
            if self._is_dialogue_termination_signal(response_text):
                logger.warning(f"🚨 Сигнал завершения диалога в чате {chat_id}: {response_text}")
                self._handle_dialogue_termination(chat_id, "crypto_negative_reaction")
                # Всё равно отправляем последнее сообщение

            # Определяем задержку на основе анализа (упрощенно)
            context = db_manager.get_chat_context(chat_id)
            current_hour = datetime.now().hour

            # Базовая задержка для реалистичности
            delay = get_smart_delay(current_hour, 'нейтральный',
                                    context.relationship_stage if context else 'initial')

            # Добавляем в очередь ответов
            send_time = datetime.utcnow() + timedelta(seconds=delay)

            self.response_queue.append({
                'chat_id': chat_id,
                'telegram_user_id': chat.telegram_user_id,
                'message_text': response_text,
                'send_time': send_time,
                'message_batch': message_batch,
                'delay_reason': f"smart_delay(реалистичность, {current_hour}h)"
            })

            # Обновляем ID последнего обработанного сообщения
            self.last_processed_message_ids[chat_id] = message_batch.messages[-1].id
            self.stats['processed_message_batches'] += 1

            logger.info(f"📅 Ответ запланирован для чата {chat_id} через {delay}с")

        except Exception as e:
            logger.error(f"Ошибка умной обработки чата {chat.id}: {e}")

    def _is_dialogue_termination_signal(self, response_text: str) -> bool:
        """Проверка является ли ответ сигналом завершения диалога"""
        termination_phrases = [
            "каждому своё",
            "удачи тебе",
            "понятно, не твоё",
            "всего хорошего"
        ]

        response_lower = response_text.lower()
        return any(phrase in response_lower for phrase in termination_phrases)

    def _handle_dialogue_termination(self, chat_id: int, reason: str):
        """Обработка завершения диалога"""
        try:
            # Обновляем аналитику диалога
            db_manager.update_dialogue_outcome(chat_id, "failure", reason)

            # Деактивируем чат
            with db_manager.get_session() as session:
                chat = session.query(Chat).filter(Chat.id == chat_id).first()
                if chat:
                    chat.is_active = False
                    session.commit()

            logger.warning(f"🔚 Диалог {chat_id} завершен по причине: {reason}")

        except Exception as e:
            logger.error(f"❌ Ошибка завершения диалога: {e}")
    
    def _detect_batch_emotion(self, message_batch: MessageBatch) -> str:
        """Быстрое определение эмоции из пакета сообщений"""
        combined_text = message_batch.total_text.lower()
        
        negative_words = ['плохо', 'грустно', 'устала', 'проблема', 'болит']
        positive_words = ['отлично', 'супер', 'классно', 'рада', 'счастлива']
        
        if any(word in combined_text for word in negative_words):
            return 'негативный'
        elif any(word in combined_text for word in positive_words):
            return 'позитивный'
        else:
            return 'нейтральный'
    
    async def _process_response_queue(self):
        """Обработка очереди ответов с гарантией доставки"""
        current_time = datetime.utcnow()
        
        # Сортируем по времени отправки
        self.response_queue.sort(key=lambda x: x['send_time'])
        
        responses_to_send = []
        remaining_responses = []
        
        for response in self.response_queue:
            if response['send_time'] <= current_time:
                responses_to_send.append(response)
            else:
                remaining_responses.append(response)
        
        self.response_queue = remaining_responses
        
        # Отправляем готовые ответы
        for response in responses_to_send:
            await self._send_response_with_guarantee(response)
    
    async def _send_response_with_guarantee(self, response: Dict):
        """Отправка ответа с гарантией доставки"""
        try:
            chat_id = response['chat_id']
            telegram_user_id = response['telegram_user_id']
            message_text = response['message_text']
            message_batch = response['message_batch']
            
            # Убеждаемся что клиент подключен
            if not await self.telegram_client.ensure_connection():
                logger.error(f"Не удалось обеспечить подключение для отправки в чат {chat_id}")
                self.stats['failed_responses'] += 1
                return
            
            # Отправляем сообщение (внутри уже есть прочтение и typing)
            success = await self.telegram_client.send_message(
                telegram_user_id,
                message_text
            )
            
            if success:
                # Сохраняем отправленное сообщение в БД
                db_manager.add_message(
                    chat_id=chat_id,
                    text=message_text,
                    is_from_ai=True
                )
                
                # Отмечаем пакет как обработанный
                db_manager.mark_messages_as_processed(message_batch)
                
                self.stats['sent_responses'] += 1
                logger.info(f"✅ Ответ отправлен в чат {chat_id}: {message_text[:50]}...")
            else:
                logger.warning(f"❌ Не удалось отправить ответ в чат {chat_id}")
                self.stats['failed_responses'] += 1
                
        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}")
            self.stats['failed_responses'] += 1
    
    async def send_manual_message(self, user_id: int, message: str) -> bool:
        """Ручная отправка сообщения"""
        try:
            # Убеждаемся что клиент подключен
            if not await self.telegram_client.ensure_connection():
                logger.error("Не удалось обеспечить подключение для ручной отправки")
                return False
            
            success = await self.telegram_client.send_message(user_id, message)
            
            if success:
                # Находим чат в БД
                chat = db_manager.get_or_create_chat(telegram_user_id=user_id)
                
                # Сохраняем сообщение
                db_manager.add_message(
                    chat_id=chat.id,
                    text=message,
                    is_from_ai=True
                )
                
                logger.info(f"✅ Ручное сообщение отправлено пользователю {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка ручной отправки сообщения: {e}")
            return False
    
    def _log_stats(self):
        """Логирование статистики каждые N итераций"""
        # Логируем статистику каждые 10 минут
        if self.stats['processed_chats'] % 60 == 0 and self.stats['processed_chats'] > 0:
            logger.info(f"📊 Статистика: чаты={self.stats['processed_chats']}, "
                       f"пакеты={self.stats['processed_message_batches']}, "
                       f"отправлено={self.stats['sent_responses']}, "
                       f"ошибок={self.stats['failed_responses']}, "
                       f"переподключений={self.stats['reconnections']}")
    
    def get_status(self) -> Dict[str, Any]:
        """Получить расширенный статус мониторинга"""
        telegram_status = self.telegram_client.get_status()
        
        return {
            'monitoring': self.is_monitoring,
            'telegram_connected': telegram_status['connected'],
            'telegram_running': telegram_status['running'],
            'response_queue_size': len(self.response_queue),
            'active_chats': len(db_manager.get_active_chats()),
            'processed_message_ids_count': len(self.last_processed_message_ids),
            'stats': self.stats.copy(),
            'telegram_stats': telegram_status.get('stats', {}),
            'settings': {
                'monitor_interval': settings.monitor_interval,
                'message_grouping_window': self.message_grouping_window,
                'max_concurrent_chats': self.max_concurrent_chats
            }
        }
    
    async def get_dialogs(self) -> List[Dict[str, Any]]:
        """Получить список диалогов"""
        if not await self.telegram_client.ensure_connection():
            return []
        
        return await self.telegram_client.get_dialogs()
    
    def get_queue_info(self) -> List[Dict[str, Any]]:
        """Получить информацию об очереди ответов"""
        queue_info = []
        current_time = datetime.utcnow()
        
        for response in sorted(self.response_queue, key=lambda x: x['send_time']):
            time_to_send = (response['send_time'] - current_time).total_seconds()
            queue_info.append({
                'chat_id': response['chat_id'],
                'message_preview': response['message_text'][:50] + "...",
                'time_to_send_seconds': max(0, time_to_send),
                'delay_reason': response.get('delay_reason', 'unknown')
            })
        
        return queue_info

    def get_analytics_status(self) -> Dict[str, Any]:
        """Получить статус аналитики диалогов"""
        try:
            analytics_summary = db_manager.get_analytics_summary()

            return {
                "total_active_chats": len(db_manager.get_active_chats()),
                "analytics_summary": analytics_summary,
                "current_queue_size": len(self.response_queue),
                "processing_stats": self.stats.copy()
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса аналитики: {e}")
            return {}