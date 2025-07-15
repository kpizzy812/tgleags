"""
Клиент для работы с Telegram через Telethon
"""
import asyncio
from typing import Optional, List, Dict, Any
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from loguru import logger

from ..config.settings import settings, get_session_path
from ..database.database import db_manager
from ..utils.helpers import simulate_typing


class TelegramAIClient:
    """Клиент Telegram с ИИ функционалом"""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.is_running = False
        self.session_path = get_session_path()
        
    async def initialize(self) -> bool:
        """Инициализация клиента"""
        try:
            self.client = TelegramClient(
                self.session_path,
                settings.telegram_api_id,
                settings.telegram_api_hash
            )
            
            logger.info("Инициализация Telegram клиента...")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации клиента: {e}")
            return False
    
    async def connect(self) -> bool:
        """Подключение к Telegram"""
        try:
            if not self.client:
                await self.initialize()
            
            await self.client.connect()
            
            # Проверяем авторизацию
            if not await self.client.is_user_authorized():
                logger.info("Требуется авторизация...")
                await self._authorize()
            
            # Получаем информацию о себе
            me = await self.client.get_me()
            logger.info(f"Подключен как: {me.first_name} (@{me.username})")
            
            # Настраиваем обработчики событий
            self._setup_event_handlers()
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            return False
    
    async def _authorize(self):
        """Авторизация в Telegram"""
        try:
            # Отправляем код
            await self.client.send_code_request(settings.telegram_phone)
            logger.info(f"Код отправлен на номер: {settings.telegram_phone}")
            
            # Запрашиваем код у пользователя
            code = input("Введите код из SMS: ")
            
            try:
                await self.client.sign_in(settings.telegram_phone, code)
                logger.info("Авторизация успешна!")
                
            except Exception as e:
                # Возможно нужен пароль 2FA
                if "password" in str(e).lower():
                    password = input("Введите пароль 2FA: ")
                    await self.client.sign_in(password=password)
                    logger.info("Авторизация с 2FA успешна!")
                else:
                    raise e
                    
        except Exception as e:
            logger.error(f"Ошибка авторизации: {e}")
            raise
    
    def _setup_event_handlers(self):
        """Настройка обработчиков событий"""
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            """Обработка новых сообщений"""
            try:
                # Игнорируем сообщения от ботов и каналов
                if event.is_channel or event.is_group:
                    return
                
                sender = await event.get_sender()
                if getattr(sender, 'bot', False):
                    return
                
                # Обрабатываем только личные сообщения
                await self._process_incoming_message(event, sender)
                
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {e}")
        
        logger.info("Обработчики событий настроены")
    
    async def _process_incoming_message(self, event, sender: User):
        """Обработка входящего сообщения"""
        try:
            # Получаем или создаем чат в БД
            chat = db_manager.get_or_create_chat(
                telegram_user_id=sender.id,
                username=getattr(sender, 'username', None),
                first_name=getattr(sender, 'first_name', None),
                last_name=getattr(sender, 'last_name', None)
            )
            
            # Сохраняем сообщение в БД
            message_text = event.message.text or ""
            db_manager.add_message(
                chat_id=chat.id,
                text=message_text,
                is_from_ai=False,
                telegram_message_id=event.message.id
            )
            
            logger.info(f"Получено сообщение от {sender.first_name} ({sender.id}): {message_text[:50]}...")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")
    
    async def send_message(self, user_id: int, text: str, reply_to_message_id: int = None) -> bool:
        """Отправка сообщения"""
        try:
            if not self.client:
                logger.error("Клиент не инициализирован")
                return False
            
            # Имитируем печатание
            async with self.client.action(user_id, 'typing'):
                await simulate_typing()
            
            # Отправляем сообщение
            message = await self.client.send_message(
                user_id,
                text,
                reply_to=reply_to_message_id
            )
            
            logger.info(f"Отправлено сообщение пользователю {user_id}: {text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False
    
    async def mark_as_read(self, user_id: int):
        """Отметить сообщения как прочитанные"""
        try:
            await self.client.send_read_acknowledge(user_id)
        except Exception as e:
            logger.error(f"Ошибка отметки как прочитано: {e}")
    
    async def get_dialogs(self) -> List[Dict[str, Any]]:
        """Получить список диалогов"""
        try:
            if not self.client:
                return []
            
            dialogs = []
            async for dialog in self.client.iter_dialogs():
                if dialog.is_user and not dialog.entity.bot:
                    dialogs.append({
                        'id': dialog.entity.id,
                        'name': dialog.name,
                        'username': getattr(dialog.entity, 'username', None),
                        'unread_count': dialog.unread_count,
                        'last_message': dialog.message.text if dialog.message else None
                    })
            
            return dialogs
            
        except Exception as e:
            logger.error(f"Ошибка получения диалогов: {e}")
            return []
    
    async def start_monitoring(self):
        """Запуск мониторинга сообщений"""
        self.is_running = True
        logger.info("Мониторинг сообщений запущен")
        
        try:
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")
        finally:
            self.is_running = False
    
    async def stop_monitoring(self):
        """Остановка мониторинга"""
        self.is_running = False
        if self.client:
            await self.client.disconnect()
        logger.info("Мониторинг остановлен")
    
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о пользователе"""
        try:
            user = await self.client.get_entity(user_id)
            return {
                'id': user.id,
                'username': getattr(user, 'username', None),
                'first_name': getattr(user, 'first_name', None),
                'last_name': getattr(user, 'last_name', None),
                'phone': getattr(user, 'phone', None),
                'is_bot': getattr(user, 'bot', False)
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о пользователе {user_id}: {e}")
            return None
    
    def is_connected(self) -> bool:
        """Проверка подключения"""
        return self.client and self.client.is_connected() if self.client else False
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус клиента"""
        return {
            'connected': self.is_connected(),
            'running': self.is_running,
            'session_exists': self.session_path and len(self.session_path) > 0
        }