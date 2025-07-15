"""
Работа с базой данных
"""
import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from loguru import logger

from ..config.settings import settings
from .models import Base, Chat, Message, ChatContext


class DatabaseManager:
    """Менеджер базы данных"""
    
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