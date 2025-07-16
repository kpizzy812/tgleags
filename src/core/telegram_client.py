"""
Клиент для работы с Telegram через Telethon (MVP версия с исправлениями)
"""
import asyncio
import random
import time
from typing import Optional, List, Dict, Any
from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneNumberInvalidError, PeerFloodError, UserDeactivatedBanError,
    ChatWriteForbiddenError, SlowModeWaitError, AuthKeyUnregisteredError
)
from telethon.tl.types import User, Chat, Channel
from loguru import logger

from ..config.settings import settings, get_session_path
from ..database.database import db_manager


class TelegramAIClient:
    """Telegram клиент для MVP с надежным подключением"""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.is_running = False
        self.session_path = get_session_path()
        
        # Rate limiting для безопасности
        self.last_request_time = 0
        self.min_request_delay = 1.5  # Минимум 1.5 сек между запросами
        
        # Статистика
        self.stats = {
            'reconnections': 0,
            'failed_requests': 0,
            'successful_requests': 0,
            'messages_sent': 0
        }
        
    async def initialize(self) -> bool:
        """Инициализация клиента"""
        try:
            self.client = TelegramClient(
                self.session_path,
                settings.telegram_api_id,
                settings.telegram_api_hash,
                
                # Настройки для избежания банов
                device_model="Desktop",
                system_version="Windows 10", 
                app_version="4.9.0",
                lang_code="en",
                system_lang_code="en-US",
                
                timeout=30,
                request_retries=1,
                connection_retries=2,
                retry_delay=2,
                flood_sleep_threshold=60,
                receive_updates=True,
                auto_reconnect=True,
            )
            
            logger.info("✅ Telegram клиент инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации клиента: {e}")
            return False
    
    async def connect(self) -> bool:
        """Подключение к Telegram"""
        try:
            if not self.client:
                if not await self.initialize():
                    return False
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.info("🔐 Требуется авторизация...")
                success = await self._authorize()
                if not success:
                    return False
            
            # Получаем информацию о себе
            me = await self.client.get_me()
            if me:
                logger.info(f"✅ Подключен как: {me.first_name} (@{me.username}) ID: {me.id}")
            
            # Настраиваем обработчики событий для автоматического сохранения сообщений
            self._setup_event_handlers()
            
            return True
            
        except UserDeactivatedBanError:
            logger.error("❌ АККАУНТ ЗАБАНЕН!")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            return False
    
    async def ensure_connection(self) -> bool:
        """Проверка и восстановление подключения"""
        if not self.client:
            return await self.connect()
        
        if not self.client.is_connected():
            logger.warning("🔄 Переподключаемся к Telegram...")
            try:
                await self.client.connect()
                return True
            except Exception as e:
                logger.error(f"❌ Ошибка переподключения: {e}")
                self.stats['reconnections'] += 1
                return False
        
        return True
    
    async def _authorize(self) -> bool:
        """Авторизация пользователя"""
        try:
            await self._rate_limit()
            await self.client.send_code_request(settings.telegram_phone)
            logger.info(f"📱 Код отправлен на номер: {settings.telegram_phone}")
            
            code = input("Введите код из SMS: ")
            
            try:
                await self._rate_limit()
                await self.client.sign_in(settings.telegram_phone, code)
                logger.info("✅ Авторизация успешна!")
                return True
                
            except SessionPasswordNeededError:
                password = input("Введите пароль 2FA: ")
                await self._rate_limit()
                await self.client.sign_in(password=password)
                logger.info("✅ Авторизация с 2FA успешна!")
                return True
                
            except PhoneCodeInvalidError:
                logger.error("❌ Неверный код!")
                return False
                
        except FloodWaitError as e:
            logger.warning(f"⏳ Flood wait: {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации: {e}")
            return False
    
    async def _rate_limit(self):
        """Rate limiting для избежания флуда"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_delay:
            delay = self.min_request_delay - time_since_last
            await asyncio.sleep(delay)
        
        self.last_request_time = time.time()
    
    def _setup_event_handlers(self):
        """Настройка обработчиков для автоматического сохранения входящих сообщений"""
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            """Автоматическое сохранение входящих сообщений"""
            try:
                # Пропускаем группы и каналы
                if event.is_channel or event.is_group:
                    return
                
                sender = await event.get_sender()
                if not sender or getattr(sender, 'bot', False):
                    return
                
                # Сохраняем в базу данных
                await self._save_incoming_message(event, sender)
                
            except Exception as e:
                logger.error(f"❌ Ошибка обработки входящего сообщения: {e}")
        
        logger.info("🎯 Обработчики событий настроены")
    
    async def _save_incoming_message(self, event, sender: User):
        """Сохранение входящего сообщения в БД"""
        try:
            # Получаем или создаем чат
            chat = db_manager.get_or_create_chat(
                telegram_user_id=sender.id,
                username=getattr(sender, 'username', None),
                first_name=getattr(sender, 'first_name', None),
                last_name=getattr(sender, 'last_name', None)
            )
            
            # Сохраняем сообщение
            message_text = event.message.text or ""
            db_manager.add_message(
                chat_id=chat.id,
                text=message_text,
                is_from_ai=False,
                telegram_message_id=event.message.id
            )
            
            logger.info(f"📨 Получено от {sender.first_name} ({sender.id}): {message_text[:50]}...")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения сообщения: {e}")
    
    async def send_message(self, user_id: int, text: str) -> bool:
        """Отправка сообщения с реалистичной имитацией человеческого поведения"""
        try:
            if not await self.ensure_connection():
                logger.error("❌ Нет подключения для отправки сообщения")
                self.stats['failed_requests'] += 1
                return False
            
            await self._rate_limit()
            
            # 1. ПРОЧИТЫВАЕМ сообщения
            try:
                # Отмечаем сообщения как прочитанные
                await self.client.send_read_acknowledge(user_id)
                logger.debug(f"✅ Сообщения отмечены как прочитанные для {user_id}")
                
                # Реалистичная пауза после прочтения
                await asyncio.sleep(random.uniform(1.0, 4.0))
                
            except Exception as e:
                logger.debug(f"⚠️ Не удалось отметить как прочитанное: {e}")
                # Продолжаем выполнение
            
            # 2. ПОКАЗЫВАЕМ "печатает..."
            typing_duration = min(len(text) * 0.1 + random.uniform(2.0, 5.0), 10.0)
            
            try:
                # Используем правильный синтаксис для typing action
                async with self.client.action(user_id, 'typing'):
                    await asyncio.sleep(typing_duration)
                    
                logger.debug(f"⌨️ Показали 'печатает...' {typing_duration:.1f}с для {user_id}")
                
            except Exception as e:
                logger.debug(f"⚠️ Не удалось показать typing: {e}")
                # Все равно делаем паузу для реалистичности
                await asyncio.sleep(typing_duration)
            
            # 3. ОТПРАВЛЯЕМ сообщение
            await self._rate_limit()
            message = await self.client.send_message(user_id, text)
            
            if message:
                self.stats['successful_requests'] += 1
                self.stats['messages_sent'] += 1
                logger.info(f"✅ Отправлено пользователю {user_id}: {text[:50]}...")
                return True
            else:
                self.stats['failed_requests'] += 1
                logger.warning(f"❌ Не удалось отправить сообщение пользователю {user_id}")
                return False
                
        except FloodWaitError as e:
            logger.warning(f"⏳ Flood wait {e.seconds}с при отправке в {user_id}")
            await asyncio.sleep(e.seconds)
            self.stats['failed_requests'] += 1
            return False
            
        except (ChatWriteForbiddenError, PeerFloodError) as e:
            logger.error(f"🚫 Заблокирован для отправки пользователю {user_id}: {e}")
            self.stats['failed_requests'] += 1
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения пользователю {user_id}: {e}")
            self.stats['failed_requests'] += 1
            return False
    
    async def get_dialogs(self) -> List[Dict[str, Any]]:
        """Получение списка диалогов"""
        try:
            if not await self.ensure_connection():
                return []
            
            await self._rate_limit()
            
            dialogs = []
            async for dialog in self.client.iter_dialogs(limit=50):  # Ограничиваем для безопасности
                # Только личные чаты с людьми (не ботами)
                if dialog.is_user and not dialog.entity.bot:
                    dialogs.append({
                        'id': dialog.entity.id,
                        'name': dialog.name,
                        'username': getattr(dialog.entity, 'username', None),
                        'unread_count': dialog.unread_count,
                        'last_message': dialog.message.text if dialog.message else None
                    })
                
                # Небольшая пауза между итерациями
                await asyncio.sleep(0.1)
            
            logger.info(f"📋 Получено {len(dialogs)} диалогов")
            return dialogs
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения диалогов: {e}")
            return []
    
    async def start_monitoring(self):
        """Запуск мониторинга событий"""
        self.is_running = True
        logger.info("🔄 Мониторинг Telegram запущен")
        
        try:
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"❌ Ошибка мониторинга: {e}")
        finally:
            self.is_running = False
    
    async def stop_monitoring(self):
        """Остановка мониторинга"""
        self.is_running = False
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        logger.info("⏹️ Мониторинг остановлен")
    
    def is_connected(self) -> bool:
        """Проверка подключения"""
        return self.client and self.client.is_connected() if self.client else False
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус клиента"""
        return {
            'connected': self.is_connected(),
            'running': self.is_running,
            'stats': self.stats.copy()
        }