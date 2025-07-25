"""
Упрощенные модели базы данных - только самое необходимое
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Chat(Base):
    """Модель чата/диалога - базовая информация"""
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

    # Связи (только с нужными таблицами)
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    facts = relationship("PersonFact", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    """Модель сообщения - без изменений"""
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


class PersonFact(Base):
    """Простые факты о собеседнице - основа для естественного общения"""
    __tablename__ = "person_facts"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)

    # Тип и содержание факта
    fact_type = Column(String(50), nullable=False)  # "job", "financial_complaint", "expensive_dream"
    fact_value = Column(String(500), nullable=False)
    confidence = Column(Float, default=0.8)  # Уверенность в факте

    # Метаданные
    first_mentioned = Column(DateTime, default=datetime.utcnow)
    last_confirmed = Column(DateTime, default=datetime.utcnow)
    source_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)

    # Использование
    times_referenced = Column(Integer, default=0)

    # Связи
    chat = relationship("Chat", back_populates="facts")
    source_message = relationship("Message")


# УДАЛЕНО (переусложнение):
# ❌ ChatContext - сложные JSON поля, избыточная информация
# ❌ DialogueAnalytics - роботизированные метрики и скоры

# ОСТАВЛЕНО (необходимое):
# ✅ Chat - базовая информация о диалоге
# ✅ Message - история сообщений
# ✅ PersonFact - простые факты для естественного общения

"""
Типы фактов в PersonFact:

job - работа собеседницы
- "администратор", "менеджер", "продавец"

financial_complaint - жалобы на деньги
- "мало платят", "денег не хватает", "зарплата маленькая"

expensive_dream - дорогие мечты
- "хочу машину", "мечтаю путешествовать", "хочу квартиру"

other - другие важные факты
- имя, возраст, интересы, семейное положение
"""