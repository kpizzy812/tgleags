"""
Модели базы данных
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float
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
    analytics = relationship("DialogueAnalytics", back_populates="chat", cascade="all, delete-orphan")
    facts = relationship("PersonFact", back_populates="chat", cascade="all, delete-orphan")


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
    financial_profile = Column(Text)  # JSON с финансовым профилем
    emotional_profile = Column(Text)  # JSON с эмоциональным профилем
    dialogue_stage_history = Column(Text)  # JSON история этапов
    personality_notes = Column(Text, nullable=True)  # Заметки о личности
    relationship_stage = Column(String(50), default="initial")  # initial, friendly, close, etc.
    detected_interests = Column(Text, nullable=True)  # JSON массив интересов ← ДОБАВИТЬ ЭТУ СТРОКУ

    # Статистика
    messages_count = Column(Integer, default=0)
    ai_messages_count = Column(Integer, default=0)

    # Последнее обновление
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    chat = relationship("Chat", back_populates="context")

class DialogueAnalytics(Base):
    """Аналитика диалогов для обучения системы"""
    __tablename__ = "dialogue_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    
    # Этапы диалога
    current_stage = Column(String(50), default="initiation")
    stage_progression = Column(Text)  # JSON история этапов
    
    # Финансовый анализ
    financial_score = Column(Integer, default=0)  # 0-10
    financial_readiness = Column(String(50), default="отсутствует")
    money_complaints_count = Column(Integer, default=0)
    expensive_desires = Column(Text)  # JSON массив
    
    # Эмоциональный анализ  
    trust_level = Column(Integer, default=0)  # 0-10
    emotional_connection = Column(Integer, default=0)  # 0-10
    traumas_shared = Column(Text)  # JSON массив
    stas_stories_used = Column(Text)  # JSON массив использованных историй
    
    # Результаты
    work_offer_made = Column(Boolean, default=False)
    work_offer_accepted = Column(Boolean, default=False)
    dialogue_outcome = Column(String(50))  # "success", "failure", "ongoing"
    failure_reason = Column(String(200))
    
    # Метаданные
    dialogue_duration_days = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    prospect_score = Column(Integer, default=0)  # 0-100
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    chat = relationship("Chat", back_populates="analytics")


class PersonFact(Base):
    """Факты о собеседнице для персонализации"""
    __tablename__ = "person_facts"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    
    # Тип и содержание факта
    fact_type = Column(String(50), nullable=False)  # "name", "job", "salary", "dream", "trauma"
    fact_value = Column(String(500), nullable=False)
    confidence = Column(Float, default=0.8)  # Уверенность в факте
    
    # Метаданные
    first_mentioned = Column(DateTime, default=datetime.utcnow)
    last_confirmed = Column(DateTime, default=datetime.utcnow)
    source_message_id = Column(Integer, ForeignKey("messages.id"))
    
    # Использование
    times_referenced = Column(Integer, default=0)
    
    # Связи
    chat = relationship("Chat", back_populates="facts")
    source_message = relationship("Message")
