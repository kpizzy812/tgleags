"""
Мониторинг и обработка сообщений
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

from ..config.settings import settings
from ..database.database import db_manager
from ..utils.helpers import get_random_delay
from .telegram_client import TelegramAIClient
from .response_generator import ResponseGenerator


class MessageMonitor:
    """Мониторинг и автоматическая обработка сообщений"""
    
    def __init__(self):
        self.telegram_client = TelegramAIClient()
        self.response_generator = ResponseGenerator()
        self.is_monitoring = False
        self.last_processed_messages: Dict[int, int] = {}  # user_id -> last_message_id
        self.response_queue: List[Dict] = []  # Очередь ответов
        
    async def start(self) -> bool:
        """Запуск мониторинга"""
        try:
            # Инициализируем и подключаем Telegram клиент
            if not await self.telegram_client.initialize():
                logger.error("Не удалось инициализировать Telegram клиент")
                return False
            
            if not await self.telegram_client.connect():
                logger.error("Не удалось подключиться к Telegram")
                return False
            
            self.is_monitoring = True
            logger.info("Мониторинг сообщений запущен")
            
            # Запускаем основной цикл мониторинга
            await self._monitoring_loop()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка запуска мониторинга: {e}")
            return False
    
    async def stop(self):
        """Остановка мониторинга"""
        self.is_monitoring = False
        await self.telegram_client.stop_monitoring()
        logger.info("Мониторинг остановлен")
    
    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info(f"Начат мониторинг с интервалом {settings.monitor_interval} секунд")
        
        while self.is_monitoring:
            try:
                # Обрабатываем очередь ответов
                await self._process_response_queue()
                
                # Проверяем новые сообщения
                await self._check_new_messages()
                
                # Пауза перед следующей итерацией
                await asyncio.sleep(settings.monitor_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(settings.monitor_interval)
    
    async def _check_new_messages(self):
        """Проверка новых сообщений"""
        try:
            # Получаем активные чаты из БД
            active_chats = db_manager.get_active_chats()
            
            for chat in active_chats[:settings.max_concurrent_chats]:
                await self._process_chat(chat)
                
        except Exception as e:
            logger.error(f"Ошибка проверки новых сообщений: {e}")
    
    async def _process_chat(self, chat):
        """Обработка отдельного чата"""
        try:
            # Получаем последние сообщения из БД
            recent_messages = db_manager.get_chat_messages(chat.id, limit=5)
            
            if not recent_messages:
                return
            
            # Находим последнее сообщение от пользователя
            last_user_message = None
            for msg in reversed(recent_messages):
                if not msg.is_from_ai:
                    last_user_message = msg
                    break
            
            if not last_user_message or not last_user_message.text:
                return
            
            # Проверяем, нужно ли отвечать
            if not self._should_process_message(chat.id, last_user_message):
                return
            
            # Проверяем, должны ли мы ответить на это сообщение
            if not self.response_generator.should_respond(chat.id, last_user_message.text):
                logger.debug(f"Пропускаем ответ для чата {chat.id}")
                return
            
            # Генерируем ответ
            response_text = await self.response_generator.generate_response(
                chat.id, 
                last_user_message.text
            )
            
            if not response_text:
                logger.warning(f"Не удалось сгенерировать ответ для чата {chat.id}")
                return
            
            # Добавляем в очередь ответов с задержкой
            delay = get_random_delay()
            send_time = datetime.utcnow() + timedelta(seconds=delay)
            
            self.response_queue.append({
                'chat_id': chat.id,
                'telegram_user_id': chat.telegram_user_id,
                'message_text': response_text,
                'send_time': send_time,
                'reply_to_message_id': last_user_message.telegram_message_id
            })
            
            logger.info(f"Ответ запланирован для чата {chat.id} через {delay} секунд")
            
        except Exception as e:
            logger.error(f"Ошибка обработки чата {chat.id}: {e}")
    
    def _should_process_message(self, chat_id: int, message) -> bool:
        """Проверить, нужно ли обрабатывать сообщение"""
        # Проверяем, не обрабатывали ли мы уже это сообщение
        last_processed_id = self.last_processed_messages.get(chat_id, 0)
        
        if message.id <= last_processed_id:
            return False
        
        # Проверяем, не слишком ли старое сообщение
        time_diff = datetime.utcnow() - message.created_at
        if time_diff.total_seconds() > 3600:  # Не отвечаем на сообщения старше часа
            return False
        
        # Проверяем, есть ли уже ответ ИИ на это сообщение
        recent_ai_messages = db_manager.get_chat_messages(chat_id, limit=3)
        for ai_msg in recent_ai_messages:
            if ai_msg.is_from_ai and ai_msg.created_at > message.created_at:
                return False
        
        return True
    
    async def _process_response_queue(self):
        """Обработка очереди ответов"""
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
            await self._send_response(response)
    
    async def _send_response(self, response: Dict):
        """Отправка ответа"""
        try:
            chat_id = response['chat_id']
            telegram_user_id = response['telegram_user_id']
            message_text = response['message_text']
            reply_to_id = response.get('reply_to_message_id')
            
            # Отмечаем сообщения как прочитанные
            await self.telegram_client.mark_as_read(telegram_user_id)
            
            # Отправляем сообщение через Telegram
            success = await self.telegram_client.send_message(
                telegram_user_id,
                message_text,
                reply_to_id
            )
            
            if success:
                # Сохраняем отправленное сообщение в БД
                db_manager.add_message(
                    chat_id=chat_id,
                    text=message_text,
                    is_from_ai=True
                )
                
                # Обновляем последнее обработанное сообщение
                recent_messages = db_manager.get_chat_messages(chat_id, limit=1)
                if recent_messages:
                    self.last_processed_messages[chat_id] = recent_messages[0].id
                
                logger.info(f"Ответ отправлен в чат {chat_id}: {message_text[:50]}...")
            else:
                logger.warning(f"Не удалось отправить ответ в чат {chat_id}")
                
        except Exception as e:
            logger.error(f"Ошибка отправки ответа: {e}")
    
    async def send_manual_message(self, user_id: int, message: str) -> bool:
        """Ручная отправка сообщения"""
        try:
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
                
                logger.info(f"Ручное сообщение отправлено пользователю {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка ручной отправки сообщения: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус мониторинга"""
        telegram_status = self.telegram_client.get_status()
        
        return {
            'monitoring': self.is_monitoring,
            'telegram_connected': telegram_status['connected'],
            'telegram_running': telegram_status['running'],
            'response_queue_size': len(self.response_queue),
            'active_chats': len(db_manager.get_active_chats()),
            'last_processed_messages': len(self.last_processed_messages)
        }
    
    async def get_dialogs(self) -> List[Dict[str, Any]]:
        """Получить список диалогов"""
        return await self.telegram_client.get_dialogs()