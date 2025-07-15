"""
Модели базы данных
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Chat(Base):
    """Модель чата/диалога"""
    __tablename__ = "chats"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Статус чата
    is_active = Column(Boolean, default=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    context = relationship("ChatContext", back_populates="chat", uselist=False)


class Message(Base):
    """Модель сообщения"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    
    # Содержимое сообщения
    text = Column(Text, nullable=True)
    message_type = Column(String(50), default="text")  # text, photo, video, voice, etc.
    
    # Направление сообщения
    is_from_ai = Column(Boolean, default=False)
    
    # Telegram метаданные
    telegram_message_id = Column(Integer, nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    
    # Связи
    chat = relationship("Chat", back_populates="messages")


class ChatContext(Base):
    """Контекст чата для ИИ"""
    __tablename__ = "chat_contexts"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), unique=True, nullable=False)
    
    # Информация о собеседнице
    detected_interests = Column(Text, nullable=True)  # JSON массив интересов
    personality_notes = Column(Text, nullable=True)  # Заметки о личности
    relationship_stage = Column(String(50), default="initial")  # initial, friendly, close, etc.
    
    # Статистика
    messages_count = Column(Integer, default=0)
    ai_messages_count = Column(Integer, default=0)
    
    # Последнее обновление
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    chat = relationship("Chat", back_populates="context")