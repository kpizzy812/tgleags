"""
Клиент для работы с Telegram через Telethon (Улучшенная версия)
"""
import asyncio
import random
import time
from typing import Optional, List, Dict, Any, Union
from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneNumberInvalidError, PeerFloodError, UserDeactivatedBanError,
    ChatWriteForbiddenError, SlowModeWaitError, ConnectionError,
    TimeoutError, AuthKeyUnregisteredError
)
from telethon.tl.types import User, Chat, Channel
from loguru import logger

from ..config.settings import settings, get_session_path
from ..database.database import db_manager


class ConnectionManager:
    """Менеджер подключений с переподключением и прокси-поддержкой"""
    
    def __init__(self, client_instance):
        self.client = client_instance
        self.last_connection_check = 0
        self.connection_check_interval = 30  # проверка каждые 30 сек
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 10
        
    async def ensure_connected(self) -> bool:
        """Убеждаемся что клиент подключен, переподключаемся если нужно"""
        current_time = time.time()
        
        # Проверяем не слишком ли часто
        if current_time - self.last_connection_check < self.connection_check_interval:
            if self.client.client and self.client.client.is_connected():
                return True
        
        self.last_connection_check = current_time
        
        # Проверяем подключение
        if not self.client.client or not self.client.client.is_connected():
            logger.warning("🔄 Клиент отключен, пытаемся переподключиться...")
            return await self._reconnect()
        
        return True
    
    async def _reconnect(self) -> bool:
        """Переподключение с повторными попытками"""
        for attempt in range(self.max_reconnect_attempts):
            try:
                logger.info(f"🔄 Попытка переподключения {attempt + 1}/{self.max_reconnect_attempts}")
                
                # Закрываем старое соединение если есть
                if self.client.client and self.client.client.is_connected():
                    await self.client.client.disconnect()
                
                # Переподключаемся
                if not await self.client.initialize():
                    raise ConnectionError("Не удалось инициализировать клиент")
                
                if not await self.client.connect():
                    raise ConnectionError("Не удалось подключиться")
                
                logger.info("✅ Переподключение успешно")
                return True
                
            except Exception as e:
                logger.error(f"❌ Попытка {attempt + 1} не удалась: {e}")
                if attempt < self.max_reconnect_attempts - 1:
                    await asyncio.sleep(self.reconnect_delay * (attempt + 1))
        
        logger.error("❌ Все попытки переподключения исчерпаны")
        return False


class TelegramAIClient:
    """Telegram клиент с защитой от банов и стабильным подключением"""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.is_running = False
        self.session_path = get_session_path()
        self.last_request_time = 0
        self.flood_wait_until = 0
        
        # Rate limiting
        self.min_request_delay = 1
        self.flood_wait_multiplier = 1.5
        
        # Менеджер подключений
        self.connection_manager = ConnectionManager(self)
        
        # Статистика для мониторинга
        self.stats = {
            'reconnections': 0,
            'failed_requests': 0,
            'successful_requests': 0
        }
        
    async def initialize(self) -> bool:
        """Инициализация клиента с защитой от банов"""
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
                
                timeout=60,
                request_retries=2,  # Снижаем для быстрого переподключения
                connection_retries=3,
                retry_delay=3,
                flood_sleep_threshold=60,
                receive_updates=True,
                auto_reconnect=True,
            )
            
            logger.info("Инициализация защищенного Telegram клиента...")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации клиента: {e}")
            return False
    
    async def connect(self) -> bool:
        """Безопасное подключение"""
        try:
            if not self.client:
                await self.initialize()
            
            await self._wait_for_flood()
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.info("Требуется авторизация...")
                success = await self._safe_authorize()
                if not success:
                    return False
            
            me = await self._safe_api_call(self.client.get_me)
            if me:
                logger.info(f"Подключен как: {me.first_name} (@{me.username})")
                
                if await self._check_account_status():
                    logger.warning("⚠️ Аккаунт может быть ограничен!")
            
            self._setup_event_handlers()
            return True
            
        except UserDeactivatedBanError:
            logger.error("❌ АККАУНТ ЗАБАНЕН!")
            return False
        except Exception as e:
            logger.error(f"Ошибка подключения: {e}")
            return False
    
    async def ensure_connection(self) -> bool:
        """Публичный метод для проверки подключения перед операциями"""
        return await self.connection_manager.ensure_connected()
    
    async def _safe_authorize(self) -> bool:
        """Безопасная авторизация"""
        try:
            await self._wait_for_flood()
            await self.client.send_code_request(settings.telegram_phone)
            logger.info(f"Код отправлен на номер: {settings.telegram_phone}")
            
            code = input("Введите код из SMS: ")
            
            try:
                await self._wait_for_flood()
                await self.client.sign_in(settings.telegram_phone, code)
                logger.info("✅ Авторизация успешна!")
                return True
                
            except SessionPasswordNeededError:
                password = input("Введите пароль 2FA: ")
                await self._wait_for_flood()
                await self.client.sign_in(password=password)
                logger.info("✅ Авторизация с 2FA успешна!")
                return True
                
            except PhoneCodeInvalidError:
                logger.error("❌ Неверный код!")
                return False
                
        except PhoneNumberInvalidError:
            logger.error("❌ Неверный номер телефона!")
            return False
        except FloodWaitError as e:
            logger.warning(f"⏳ Flood wait: {e.seconds} секунд")
            await asyncio.sleep(e.seconds * self.flood_wait_multiplier)
            return await self._safe_authorize()
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации: {e}")
            return False
    
    async def _check_account_status(self) -> bool:
        """Проверка ограничений аккаунта"""
        try:
            await self._safe_api_call(self.client.get_entity, "@spambot")
            return False
        except PeerFloodError:
            return True
        except:
            return False
    
    async def _wait_for_flood(self):
        """Ожидание снятия flood ограничений"""
        current_time = time.time()
        
        if current_time < self.flood_wait_until:
            wait_time = self.flood_wait_until - current_time
            logger.info(f"⏳ Ожидание flood wait: {wait_time:.1f} сек")
            await asyncio.sleep(wait_time)
        
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_delay:
            delay = self.min_request_delay - time_since_last
            await asyncio.sleep(delay)
        
        self.last_request_time = time.time()
    
    async def _safe_api_call(self, func, *args, **kwargs):
        """Безопасный вызов API с переподключением"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Проверяем подключение перед вызовом
                if not await self.ensure_connection():
                    self.stats['failed_requests'] += 1
                    return None
                
                await self._wait_for_flood()
                result = await func(*args, **kwargs)
                self.stats['successful_requests'] += 1
                return result
                
            except (ConnectionError, TimeoutError, AuthKeyUnregisteredError) as e:
                logger.warning(f"⚠️ Проблема с подключением (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    if await self.connection_manager._reconnect():
                        self.stats['reconnections'] += 1
                        continue
                    
            except FloodWaitError as e:
                wait_time = e.seconds * self.flood_wait_multiplier
                logger.warning(f"⏳ Flood wait: {wait_time} сек (попытка {attempt + 1})")
                
                self.flood_wait_until = time.time() + wait_time
                await asyncio.sleep(wait_time)
                
                if attempt == max_retries - 1:
                    raise
                    
            except (PeerFloodError, ChatWriteForbiddenError) as e:
                logger.error(f"❌ Ограничения аккаунта: {e}")
                self.stats['failed_requests'] += 1
                return None
                
            except SlowModeWaitError as e:
                logger.warning(f"⏳ Slow mode: {e.seconds} сек")
                await asyncio.sleep(e.seconds)
                
            except Exception as e:
                logger.error(f"❌ Ошибка API: {e}")
                if attempt == max_retries - 1:
                    self.stats['failed_requests'] += 1
                    raise
                await asyncio.sleep(5)
        
        self.stats['failed_requests'] += 1
        return None
    
    def _setup_event_handlers(self):
        """Настройка обработчиков событий"""
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            """Обработка новых сообщений"""
            try:
                if event.is_channel or event.is_group:
                    return
                
                sender = await self._safe_api_call(event.get_sender)
                if not sender or getattr(sender, 'bot', False):
                    return
                
                await self._process_incoming_message(event, sender)
                
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения: {e}")
        
        logger.info("Обработчики событий настроены")
    
    async def _process_incoming_message(self, event, sender: User):
        """Обработка входящего сообщения"""
        try:
            chat = db_manager.get_or_create_chat(
                telegram_user_id=sender.id,
                username=getattr(sender, 'username', None),
                first_name=getattr(sender, 'first_name', None),
                last_name=getattr(sender, 'last_name', None)
            )
            
            message_text = event.message.text or ""
            db_manager.add_message(
                chat_id=chat.id,
                text=message_text,
                is_from_ai=False,
                telegram_message_id=event.message.id
            )
            
            logger.info(f"📨 Получено от {sender.first_name} ({sender.id}): {message_text[:50]}...")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения: {e}")
    
    async def send_message(self, user_id: int, text: str, reply_to_message_id: int = None) -> bool:
        """Безопасная отправка сообщения с переподключением"""
        try:
            # КРИТИЧНО: Проверяем подключение перед операцией
            if not await self.ensure_connection():
                logger.error("Не удалось обеспечить подключение для отправки сообщения")
                return False
            
            # Сначала прочитываем сообщения
            await self._safe_api_call(self.client.send_read_acknowledge, user_id)
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Показываем "печатает..."
            typing_duration = min(len(text) * 0.1, 5.0)
            async with self.client.action(user_id, 'typing'):
                await asyncio.sleep(typing_duration)
            
            # Отправляем сообщение
            message = await self._safe_api_call(
                self.client.send_message,
                user_id,
                text,
                reply_to=reply_to_message_id
            )
            
            if message:
                logger.info(f"✅ Отправлено пользователю {user_id}: {text[:50]}...")
                return True
            else:
                logger.warning(f"❌ Не удалось отправить сообщение пользователю {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения: {e}")
            return False
    
    async def mark_as_read(self, user_id: int):
        """Отметить сообщения как прочитанные"""
        try:
            if not await self.ensure_connection():
                return False
                
            await self._safe_api_call(self.client.send_read_acknowledge, user_id)
            logger.debug(f"✅ Сообщения отмечены как прочитанные для {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отметки как прочитано: {e}")
            return False
    
    async def get_dialogs(self) -> List[Dict[str, Any]]:
        """Безопасное получение диалогов"""
        try:
            if not await self.ensure_connection():
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
                
                await asyncio.sleep(0.1)  # Пауза между итерациями
            
            return dialogs
            
        except Exception as e:
            logger.error(f"Ошибка получения диалогов: {e}")
            return []
    
    async def start_monitoring(self):
        """Безопасный запуск мониторинга"""
        self.is_running = True
        logger.info("🔒 Защищенный мониторинг запущен")
        
        try:
            async with self.client:
                await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")
        finally:
            self.is_running = False
    
    async def stop_monitoring(self):
        """Безопасная остановка мониторинга"""
        self.is_running = False
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        logger.info("🔒 Мониторинг безопасно остановлен")
    
    async def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о пользователе"""
        try:
            if not await self.ensure_connection():
                return None
                
            user = await self._safe_api_call(self.client.get_entity, user_id)
            if user:
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
        """Получить расширенный статус клиента"""
        return {
            'connected': self.is_connected(),
            'running': self.is_running,
            'session_exists': bool(self.session_path),
            'flood_wait_active': time.time() < self.flood_wait_until,
            'last_request_time': self.last_request_time,
            'stats': self.stats.copy(),
            'last_connection_check': self.connection_manager.last_connection_check
        }