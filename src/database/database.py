"""
Упрощенная работа с базой данных - только необходимое
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, and_, desc
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from ..config.settings import settings
from .models import Base, Chat, Message, PersonFact


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
    """Простой менеджер базы данных"""

    def __init__(self):
        self.engine = create_engine(
            settings.database_url.replace("sqlite://", "sqlite+pysqlite://"),
            echo=False,
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._init_database()

    def _init_database(self):
        """Простая инициализация базы данных"""
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
        """Получить новые сообщения от пользователя"""
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
                if msg.created_at >= cutoff_time:
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
        """Отмечаем сообщения как обработанные"""
        # Логика реализована через add_message с is_from_ai=True
        return True

    def get_message_statistics(self, chat_id: int, days: int = 30) -> Dict[str, Any]:
        """Простая статистика сообщений"""
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
        """Получить контекст разговора для ИИ"""
        messages = self.get_chat_messages(chat_id, limit)

        context_lines = []
        for msg in messages[-limit:]:
            role = "Стас" if msg.is_from_ai else "Она"
            timestamp = msg.created_at.strftime("%H:%M")
            text = msg.text or ""
            context_lines.append(f"[{timestamp}] {role}: {text}")

        return "\n".join(context_lines)

    def get_active_chats(self) -> List[Chat]:
        """Получить активные чаты"""
        with self.get_session() as session:
            chats = session.query(Chat).filter(
                Chat.is_active == True
            ).all()
            return chats

    def get_chat_by_id(self, chat_id: int) -> Optional[Chat]:
        """Получить чат по ID"""
        try:
            with self.get_session() as session:
                chat = session.query(Chat).filter(Chat.id == chat_id).first()
                return chat
        except Exception as e:
            logger.error(f"❌ Ошибка получения чата {chat_id}: {e}")
            return None

    # =================================================================
    # РАБОТА С ФАКТАМИ О СОБЕСЕДНИЦАХ
    # =================================================================

    def save_person_fact(self, chat_id: int, fact_type: str, fact_value: str,
                        confidence: float = 0.8, source_message_id: int = None) -> bool:
        """Сохранение простого факта о собеседнице"""
        try:
            with self.get_session() as session:
                # Проверяем есть ли уже такой факт
                existing_fact = session.query(PersonFact).filter(
                    and_(
                        PersonFact.chat_id == chat_id,
                        PersonFact.fact_type == fact_type,
                        PersonFact.fact_value == fact_value
                    )
                ).first()

                if existing_fact:
                    # Обновляем существующий факт
                    existing_fact.last_confirmed = datetime.utcnow()
                    existing_fact.confidence = max(existing_fact.confidence, confidence)
                    existing_fact.times_referenced += 1
                else:
                    # Создаем новый факт
                    fact = PersonFact(
                        chat_id=chat_id,
                        fact_type=fact_type,
                        fact_value=fact_value,
                        confidence=confidence,
                        source_message_id=source_message_id
                    )
                    session.add(fact)

                session.commit()
                return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения факта: {e}")
            return False

    def get_person_facts(self, chat_id: int, fact_type: str = None) -> List[PersonFact]:
        """Получение фактов о собеседнице"""
        try:
            with self.get_session() as session:
                query = session.query(PersonFact).filter(PersonFact.chat_id == chat_id)

                if fact_type:
                    query = query.filter(PersonFact.fact_type == fact_type)

                facts = query.order_by(PersonFact.confidence.desc()).all()
                return facts

        except Exception as e:
            logger.error(f"❌ Ошибка получения фактов: {e}")
            return []

    def get_conversation_context_with_facts(self, chat_id: int, limit: int = 20) -> str:
        """Контекст диалога с фактами о собеседнице"""
        try:
            # Получаем базовый контекст
            base_context = self.get_recent_conversation_context(chat_id, limit)

            # Получаем ключевые факты
            facts = self.get_person_facts(chat_id)

            if not facts:
                return base_context

            # Добавляем краткую информацию о собеседнице
            facts_summary = "\n--- ЧТО МЫ ЗНАЕМ О НЕЙ ---\n"

            work_facts = [f for f in facts if f.fact_type == "job"]
            money_facts = [f for f in facts if f.fact_type == "financial_complaint"]
            dream_facts = [f for f in facts if f.fact_type == "expensive_dream"]

            if work_facts:
                facts_summary += f"Работа: {work_facts[0].fact_value}\n"
            if money_facts:
                facts_summary += f"Жалобы: {', '.join([f.fact_value for f in money_facts])}\n"
            if dream_facts:
                facts_summary += f"Мечты: {', '.join([f.fact_value for f in dream_facts])}\n"

            return f"{base_context}\n{facts_summary}"

        except Exception as e:
            logger.error(f"❌ Ошибка получения контекста с фактами: {e}")
            return self.get_recent_conversation_context(chat_id, limit)

    # =================================================================
    # УТИЛИТЫ
    # =================================================================

    def cleanup_old_messages(self, days_to_keep: int = 30) -> int:
        """Очистка старых сообщений"""
        with self.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            deleted_count = session.query(Message).filter(
                Message.created_at < cutoff_date
            ).delete()

            session.commit()
            logger.info(f"Удалено {deleted_count} старых сообщений")
            return deleted_count

    def deactivate_chat(self, chat_id: int, reason: str = "terminated"):
        """Деактивация чата"""
        try:
            with self.get_session() as session:
                chat = session.query(Chat).filter(Chat.id == chat_id).first()
                if chat:
                    chat.is_active = False
                    session.commit()
                    logger.info(f"Чат {chat_id} деактивирован: {reason}")
        except Exception as e:
            logger.error(f"❌ Ошибка деактивации чата: {e}")

    def get_unanswered_chats(self, hours_threshold: int = 2) -> List[Chat]:
        """Получить чаты с неотвеченными сообщениями"""
        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_threshold)

            unanswered_chats = []
            active_chats = session.query(Chat).filter(Chat.is_active == True).all()

            for chat in active_chats:
                # Получаем последнее сообщение
                last_message = session.query(Message).filter(
                    Message.chat_id == chat.id
                ).order_by(Message.created_at.desc()).first()

                if (last_message and
                    not last_message.is_from_ai and
                    last_message.created_at < cutoff_time):
                    unanswered_chats.append(chat)

            return unanswered_chats


# УДАЛЕНО (переусложнение):
# ❌ save_dialogue_analysis() - сложная аналитика
# ❌ get_dialogue_analytics() - роботизированные метрики
# ❌ get_analytics_summary() - избыточная статистика
# ❌ update_dialogue_outcome() - механистичная логика
# ❌ get_high_prospect_chats() - скоры и оценки
# ❌ mark_dialogue_success() - формальные метрики
# ❌ update_chat_context() - сложные JSON поля
# ❌ get_chat_context() - избыточная информация

# ОСТАВЛЕНО (необходимое):
# ✅ Основная работа с чатами и сообщениями
# ✅ Простое сохранение и получение фактов
# ✅ Контекст диалога для ИИ
# ✅ Базовая статистика сообщений
# ✅ Утилиты для обслуживания

# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()