"""
Работа с базой данных (Улучшенная версия)
"""
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import create_engine, and_, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from loguru import logger

from ..config.settings import settings
from .models import Base, Chat, Message, ChatContext


class MessageBatch:
    """Класс для работы с пакетами сообщений"""
    
    def __init__(self, messages: List[Message], time_window: int = 30):
        self.messages = messages
        self.time_window = time_window
        self.total_text = self._combine_messages()
        self.first_message_time = messages[0].created_at if messages else None
        self.last_message_time = messages[-1].created_at if messages else None
    
    def _combine_messages(self) -> str:
        """Объединяем множественные сообщения в одну строку"""
        if not self.messages:
            return ""
        
        if len(self.messages) == 1:
            return self.messages[0].text or ""
        
        # Группируем сообщения с временными метками
        combined = []
        for msg in self.messages:
            if msg.text:
                time_str = msg.created_at.strftime("%H:%M:%S")
                combined.append(f"[{time_str}] {msg.text}")
        
        return "\n".join(combined)
    
    def get_context_summary(self) -> str:
        """Получаем краткое описание пакета для логов"""
        count = len(self.messages)
        if count == 1:
            return f"1 сообщение: {self.total_text[:50]}..."
        else:
            return f"{count} сообщений за {self.time_window}с: {self.total_text[:50]}..."


class DatabaseManager:
    """Менеджер базы данных с поддержкой группировки сообщений"""
    
    def __init__(self):
        # Создаем синхронные подключения для простоты в MVP
        self.engine = create_engine(
            settings.database_url.replace("sqlite://", "sqlite+pysqlite://"),
            echo=(settings.log_level == "DEBUG"),
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._init_database()
    
    def _init_database(self):
        """Инициализация базы данных"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("База данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    def get_session(self) -> Session:
        """Получить сессию БД"""
        return self.SessionLocal()
    
    def get_or_create_chat(self, telegram_user_id: int, username: str = None, 
                          first_name: str = None, last_name: str = None) -> Chat:
        """Получить или создать чат"""
        with self.get_session() as session:
            # Ищем существующий чат
            chat = session.query(Chat).filter(
                Chat.telegram_user_id == telegram_user_id
            ).first()
            
            if chat:
                # Обновляем информацию о пользователе
                if username:
                    chat.username = username
                if first_name:
                    chat.first_name = first_name
                if last_name:
                    chat.last_name = last_name
                chat.last_message_at = datetime.utcnow()
            else:
                # Создаем новый чат
                chat = Chat(
                    telegram_user_id=telegram_user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(chat)
                session.flush()
                
                # Создаем контекст для нового чата
                context = ChatContext(chat_id=chat.id)
                session.add(context)
            
            session.commit()
            session.refresh(chat)
            return chat
    
    def add_message(self, chat_id: int, text: str, is_from_ai: bool = False, 
                   message_type: str = "text", telegram_message_id: int = None) -> Message:
        """Добавить сообщение"""
        with self.get_session() as session:
            message = Message(
                chat_id=chat_id,
                text=text,
                is_from_ai=is_from_ai,
                message_type=message_type,
                telegram_message_id=telegram_message_id,
                sent_at=datetime.utcnow() if is_from_ai else None
            )
            session.add(message)
            
            # Обновляем статистику в контексте
            context = session.query(ChatContext).filter(
                ChatContext.chat_id == chat_id
            ).first()
            
            if context:
                context.messages_count += 1
                if is_from_ai:
                    context.ai_messages_count += 1
                context.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(message)
            return message
    
    def get_chat_messages(self, chat_id: int, limit: int = 50) -> List[Message]:
        """Получить последние сообщения чата"""
        with self.get_session() as session:
            messages = session.query(Message).filter(
                Message.chat_id == chat_id
            ).order_by(Message.created_at.desc()).limit(limit).all()
            
            return list(reversed(messages))
    
    def get_unprocessed_user_messages(self, chat_id: int, 
                                    last_processed_id: int = 0,
                                    time_window_seconds: int = 30) -> MessageBatch:
        """
        Получить все необработанные сообщения от пользователя за указанный период
        
        Args:
            chat_id: ID чата
            last_processed_id: ID последнего обработанного сообщения
            time_window_seconds: Временное окно для группировки (секунды)
        
        Returns:
            MessageBatch: Пакет сообщений для обработки
        """
        with self.get_session() as session:
            # Находим все новые сообщения от пользователя
            new_messages = session.query(Message).filter(
                and_(
                    Message.chat_id == chat_id,
                    Message.is_from_ai == False,
                    Message.id > last_processed_id
                )
            ).order_by(Message.created_at.asc()).all()
            
            if not new_messages:
                return MessageBatch([])
            
            # Группируем сообщения по временному окну
            current_time = datetime.utcnow()
            cutoff_time = current_time - timedelta(seconds=time_window_seconds)
            
            # Берем сообщения в пределах временного окна
            batched_messages = []
            for msg in new_messages:
                # Проверяем не слишком ли старое сообщение
                if msg.created_at < cutoff_time:
                    continue
                    
                batched_messages.append(msg)
            
            # Если нет сообщений в окне, берем самое новое
            if not batched_messages and new_messages:
                batched_messages = [new_messages[-1]]
            
            return MessageBatch(batched_messages, time_window_seconds)
    
    def get_last_processed_message_id(self, chat_id: int) -> int:
        """Получить ID последнего обработанного сообщения"""
        with self.get_session() as session:
            # Ищем последнее сообщение от ИИ как маркер обработки
            last_ai_message = session.query(Message).filter(
                and_(
                    Message.chat_id == chat_id,
                    Message.is_from_ai == True
                )
            ).order_by(Message.created_at.desc()).first()
            
            if not last_ai_message:
                return 0
            
            # Ищем последнее сообщение пользователя перед этим ответом ИИ
            last_user_message = session.query(Message).filter(
                and_(
                    Message.chat_id == chat_id,
                    Message.is_from_ai == False,
                    Message.created_at <= last_ai_message.created_at
                )
            ).order_by(Message.created_at.desc()).first()
            
            return last_user_message.id if last_user_message else 0
    
    def mark_messages_as_processed(self, message_batch: MessageBatch) -> bool:
        """
        Отмечаем сообщения как обработанные (через создание ответа ИИ)
        Этот метод вызывается после успешной отправки ответа
        """
        # Логика уже реализована через add_message с is_from_ai=True
        # Это автоматически служит маркером обработки
        return True
    
    def get_message_statistics(self, chat_id: int, days: int = 7) -> Dict[str, Any]:
        """Получить статистику сообщений за период"""
        with self.get_session() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Общее количество сообщений
            total_messages = session.query(Message).filter(
                and_(
                    Message.chat_id == chat_id,
                    Message.created_at >= start_date
                )
            ).count()
            
            # Сообщения от пользователя
            user_messages = session.query(Message).filter(
                and_(
                    Message.chat_id == chat_id,
                    Message.is_from_ai == False,
                    Message.created_at >= start_date
                )
            ).count()
            
            # Сообщения от ИИ
            ai_messages = session.query(Message).filter(
                and_(
                    Message.chat_id == chat_id,
                    Message.is_from_ai == True,
                    Message.created_at >= start_date
                )
            ).count()
            
            return {
                'total_messages': total_messages,
                'user_messages': user_messages,
                'ai_messages': ai_messages,
                'response_rate': ai_messages / user_messages if user_messages > 0 else 0,
                'period_days': days
            }
    
    def get_recent_conversation_context(self, chat_id: int, limit: int = 20) -> str:
        """Получить недавний контекст разговора для ИИ"""
        messages = self.get_chat_messages(chat_id, limit)
        
        context_lines = []
        for msg in messages[-limit:]:  # Берем последние сообщения
            role = "ИИ" if msg.is_from_ai else "Пользователь"
            timestamp = msg.created_at.strftime("%H:%M")
            text = msg.text or ""
            context_lines.append(f"[{timestamp}] {role}: {text}")
        
        return "\n".join(context_lines)
    
    def cleanup_old_messages(self, days_to_keep: int = 30) -> int:
        """Очистка старых сообщений для экономии места"""
        with self.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            deleted_count = session.query(Message).filter(
                Message.created_at < cutoff_date
            ).delete()
            
            session.commit()
            logger.info(f"Удалено {deleted_count} старых сообщений")
            return deleted_count
    
    def get_active_chats(self) -> List[Chat]:
        """Получить активные чаты"""
        with self.get_session() as session:
            chats = session.query(Chat).filter(
                Chat.is_active == True
            ).all()
            return chats
    
    def update_chat_context(self, chat_id: int, **kwargs):
        """Обновить контекст чата"""
        with self.get_session() as session:
            context = session.query(ChatContext).filter(
                ChatContext.chat_id == chat_id
            ).first()
            
            if context:
                for key, value in kwargs.items():
                    if hasattr(context, key):
                        setattr(context, key, value)
                context.updated_at = datetime.utcnow()
                session.commit()
    
    def get_chat_context(self, chat_id: int) -> Optional[ChatContext]:
        """Получить контекст чата"""
        with self.get_session() as session:
            context = session.query(ChatContext).filter(
                ChatContext.chat_id == chat_id
            ).first()
            return context


# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()