"""
Работа с базой данных
"""
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import create_engine, and_, desc, func, text
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from ..config.settings import settings
from .models import Base, Chat, Message, ChatContext, DialogueAnalytics, PersonFact


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
        """Инициализация базы данных с миграцией"""
        try:
            Base.metadata.create_all(bind=self.engine)

            # Проверяем и добавляем недостающие столбцы
            self._migrate_schema_if_needed()

            logger.info("База данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise

    def _migrate_schema_if_needed(self):
        """Миграция схемы БД для добавления новых столбцов"""
        try:
            with self.get_session() as session:
                # Проверяем наличие новых столбцов в chat_contexts
                try:
                    session.execute(text("SELECT financial_profile FROM chat_contexts LIMIT 1"))
                except Exception:
                    logger.info("Добавляем недостающие столбцы в chat_contexts...")

                    # Список новых столбцов для добавления
                    new_columns = [
                        "ALTER TABLE chat_contexts ADD COLUMN financial_profile TEXT",
                        "ALTER TABLE chat_contexts ADD COLUMN emotional_profile TEXT",
                        "ALTER TABLE chat_contexts ADD COLUMN dialogue_stage_history TEXT"
                    ]

                    for sql in new_columns:
                        try:
                            session.execute(sql)
                            session.commit()
                        except Exception as e:
                            # Столбец уже существует - это нормально
                            session.rollback()
                            continue

                    logger.info("Миграция chat_contexts завершена")

                # Проверяем таблицу dialogue_analytics
                try:
                    session.execute(text("SELECT prospect_score FROM dialogue_analytics LIMIT 1"))
                except Exception:
                    logger.info("Создаем таблицу dialogue_analytics...")
                    # Будет создана автоматически через create_all

        except Exception as e:
            logger.warning(f"Предупреждение миграции БД: {e}")
            logger.info("Для чистой установки удалите файл telegram_ai.db")
    
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
    
    def get_conversation_stats(self, chat_id: int) -> Dict[str, Any]:
        """Получить статистику разговора"""
        with self.get_session() as session:
            # Общее количество сообщений
            total_messages = session.query(Message).filter(
                Message.chat_id == chat_id
            ).count()
            
            # Сообщения от пользователя
            user_messages = session.query(Message).filter(
                and_(
                    Message.chat_id == chat_id,
                    Message.is_from_ai == False
                )
            ).count()
            
            # Сообщения от ИИ
            ai_messages = session.query(Message).filter(
                and_(
                    Message.chat_id == chat_id,
                    Message.is_from_ai == True
                )
            ).count()
            
            # Первое и последнее сообщение
            first_message = session.query(Message).filter(
                Message.chat_id == chat_id
            ).order_by(Message.created_at.asc()).first()
            
            last_message = session.query(Message).filter(
                Message.chat_id == chat_id
            ).order_by(Message.created_at.desc()).first()
            
            # Длительность разговора
            conversation_duration_seconds = 0
            messages_per_day = 0
            
            if first_message and last_message:
                duration = last_message.created_at - first_message.created_at
                conversation_duration_seconds = duration.total_seconds()
                
                if conversation_duration_seconds > 0:
                    days = max(1, conversation_duration_seconds / 86400)  # 86400 сек в дне
                    messages_per_day = total_messages / days
            
            return {
                'total_messages': total_messages,
                'user_messages': user_messages,
                'ai_messages': ai_messages,
                'response_rate': ai_messages / user_messages if user_messages > 0 else 0,
                'conversation_duration_seconds': conversation_duration_seconds,
                'messages_per_day': messages_per_day
            }
    
    def get_unanswered_chats(self, hours_threshold: int = 2) -> List[Chat]:
        """Получить чаты с неотвеченными сообщениями"""
        with self.get_session() as session:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_threshold)
            
            # Ищем чаты где последнее сообщение от пользователя и нет ответа от ИИ
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

    def save_dialogue_analysis(self, chat_id: int, analysis_data: Dict) -> bool:
        """Сохранение результатов анализа диалога"""
        try:
            with self.get_session() as session:
                # Получаем или создаем запись аналитики
                analytics = session.query(DialogueAnalytics).filter(
                    DialogueAnalytics.chat_id == chat_id
                ).first()

                if not analytics:
                    analytics = DialogueAnalytics(chat_id=chat_id)
                    session.add(analytics)

                # Обновляем данные из анализа
                stage_analysis = analysis_data.get("stage_analysis", {})
                financial_analysis = analysis_data.get("financial_analysis", {})
                emotional_analysis = analysis_data.get("emotional_analysis", {})
                overall_metrics = analysis_data.get("overall_metrics", {})

                # Этапы диалога
                analytics.current_stage = stage_analysis.get("current_stage", "initiation")
                analytics.dialogue_duration_days = stage_analysis.get("dialogue_day", 1)

                # Финансовые метрики
                analytics.financial_score = financial_analysis.get("overall_score", 0)
                analytics.financial_readiness = financial_analysis.get("readiness_level", "отсутствует")

                # Сохраняем дорогие желания как JSON
                expensive_desires = financial_analysis.get("expensive_desires", [])
                analytics.expensive_desires = json.dumps(expensive_desires) if expensive_desires else None

                # Подсчитываем жалобы на деньги - ИСПРАВЛЕНО
                complaint_scores = financial_analysis.get("complaint_scores", {})
                analytics.money_complaints_count = sum(complaint_scores.values()) if complaint_scores else 0

                # Эмоциональные метрики
                analytics.trust_level = emotional_analysis.get("trust_level", 0)
                analytics.emotional_connection = emotional_analysis.get("emotional_connection", 0)

                # Сохраняем травмы как JSON - ИСПРАВЛЕНО
                traumas = emotional_analysis.get("emotional_analysis", {}).get("traumas_shared", [])
                analytics.traumas_shared = json.dumps(traumas) if traumas else None

                # Общие метрики
                analytics.prospect_score = overall_metrics.get("overall_prospect_score", 0)

                # Подсчитываем общее количество сообщений - ДОБАВЛЕНО
                total_messages = session.query(Message).filter(Message.chat_id == chat_id).count()
                analytics.total_messages = total_messages

                analytics.updated_at = datetime.utcnow()

                session.commit()
                return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения анализа диалога: {e}")
            return False

    def get_chat_by_id(self, chat_id: int) -> Optional[Chat]:
        """Получить чат по ID"""
        try:
            with self.get_session() as session:
                chat = session.query(Chat).filter(Chat.id == chat_id).first()
                return chat
        except Exception as e:
            logger.error(f"❌ Ошибка получения чата {chat_id}: {e}")
            return None

    def get_high_prospect_chats(self, min_score: int = 70, limit: int = 10) -> List[DialogueAnalytics]:
        """Получить чаты с высоким скором перспективности"""
        try:
            with self.get_session() as session:
                prospects = session.query(DialogueAnalytics).join(Chat).filter(
                    and_(
                        DialogueAnalytics.prospect_score >= min_score,
                        Chat.is_active == True,
                        DialogueAnalytics.dialogue_outcome.is_(None)  # Только активные диалоги
                    )
                ).order_by(DialogueAnalytics.prospect_score.desc()).limit(limit).all()

                return prospects

        except Exception as e:
            logger.error(f"❌ Ошибка получения перспективных чатов: {e}")
            return []

    def mark_dialogue_success(self, chat_id: int, work_offer_accepted: bool = True):
        """Отметить диалог как успешный"""
        try:
            with self.get_session() as session:
                analytics = session.query(DialogueAnalytics).filter(
                    DialogueAnalytics.chat_id == chat_id
                ).first()

                if analytics:
                    analytics.dialogue_outcome = "success"
                    analytics.work_offer_made = True
                    analytics.work_offer_accepted = work_offer_accepted
                    analytics.updated_at = datetime.utcnow()
                    session.commit()

                    logger.info(f"✅ Диалог {chat_id} отмечен как успешный")

        except Exception as e:
            logger.error(f"❌ Ошибка отметки успеха диалога: {e}")

    def cleanup_old_analytics(self, days_to_keep: int = 90) -> int:
        """Очистка старой аналитики"""
        try:
            with self.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

                # Удаляем только завершенные диалоги старше указанного срока
                deleted_count = session.query(DialogueAnalytics).filter(
                    and_(
                        DialogueAnalytics.created_at < cutoff_date,
                        DialogueAnalytics.dialogue_outcome.isnot(None)
                    )
                ).delete()

                session.commit()
                logger.info(f"Удалено {deleted_count} записей старой аналитики")
                return deleted_count

        except Exception as e:
            logger.error(f"❌ Ошибка очистки аналитики: {e}")
            return 0

    def save_person_fact(self, chat_id: int, fact_type: str, fact_value: str, 
                        confidence: float = 0.8, source_message_id: int = None) -> bool:
        """Сохранение факта о собеседнице"""
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

    def get_dialogue_analytics(self, chat_id: int) -> Optional[DialogueAnalytics]:
        """Получение аналитики диалога"""
        try:
            with self.get_session() as session:
                analytics = session.query(DialogueAnalytics).filter(
                    DialogueAnalytics.chat_id == chat_id
                ).first()
                return analytics
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения аналитики: {e}")
            return None

    def update_dialogue_outcome(self, chat_id: int, outcome: str, failure_reason: str = None):
        """Обновление результата диалога"""
        try:
            with self.get_session() as session:
                analytics = session.query(DialogueAnalytics).filter(
                    DialogueAnalytics.chat_id == chat_id
                ).first()
                
                if analytics:
                    analytics.dialogue_outcome = outcome
                    if failure_reason:
                        analytics.failure_reason = failure_reason
                    analytics.updated_at = datetime.utcnow()
                    session.commit()
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обновления результата диалога: {e}")

    def get_conversation_context_with_facts(self, chat_id: int, limit: int = 50) -> str:
        """Улучшенный контекст диалога с фактами о собеседнице"""
        try:
            # Получаем базовый контекст
            base_context = self.get_recent_conversation_context(chat_id, limit)
            
            # Получаем ключевые факты
            facts = self.get_person_facts(chat_id)
            
            if not facts:
                return base_context
            
            # Добавляем информацию о собеседнице
            facts_summary = "\n--- ИЗВЕСТНЫЕ ФАКТЫ О НЕЙ ---\n"
            
            fact_groups = {}
            for fact in facts[:10]:  # Топ 10 фактов
                if fact.fact_type not in fact_groups:
                    fact_groups[fact.fact_type] = []
                fact_groups[fact.fact_type].append(fact.fact_value)
            
            for fact_type, values in fact_groups.items():
                facts_summary += f"• {fact_type}: {', '.join(values)}\n"
            
            return f"{base_context}\n{facts_summary}"
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения контекста с фактами: {e}")
            return self.get_recent_conversation_context(chat_id, limit)

    def get_analytics_summary(self) -> Dict:
        """Получение общей аналитики по всем диалогам"""
        try:
            with self.get_session() as session:
                # Общие метрики
                total_chats = session.query(DialogueAnalytics).count()

                if total_chats == 0:
                    return {
                        "total_chats": 0,
                        "stage_distribution": {},
                        "outcome_distribution": {},
                        "average_prospect_score": 0,
                        "average_trust_level": 0
                    }

                # По этапам - ИСПРАВЛЕННАЯ ВЕРСИЯ
                stage_stats = session.query(
                    DialogueAnalytics.current_stage,
                    func.count(DialogueAnalytics.id).label('count')
                ).group_by(DialogueAnalytics.current_stage).all()

                # По результатам - ИСПРАВЛЕННАЯ ВЕРСИЯ
                outcome_stats = session.query(
                    DialogueAnalytics.dialogue_outcome,
                    func.count(DialogueAnalytics.id).label('count')
                ).filter(DialogueAnalytics.dialogue_outcome.isnot(None)).group_by(
                    DialogueAnalytics.dialogue_outcome
                ).all()

                # Средние скоры - ИСПРАВЛЕННАЯ ВЕРСИЯ
                avg_prospect_score = session.query(
                    func.avg(DialogueAnalytics.prospect_score)
                ).scalar() or 0

                avg_trust_level = session.query(
                    func.avg(DialogueAnalytics.trust_level)
                ).scalar() or 0

                return {
                    "total_chats": total_chats,
                    "stage_distribution": {stage: count for stage, count in stage_stats},
                    "outcome_distribution": {outcome: count for outcome, count in outcome_stats},
                    "average_prospect_score": round(float(avg_prospect_score), 1),
                    "average_trust_level": round(float(avg_trust_level), 1)
                }

        except Exception as e:
            logger.error(f"❌ Ошибка получения аналитики: {e}")
            return {
                "total_chats": 0,
                "stage_distribution": {},
                "outcome_distribution": {},
                "average_prospect_score": 0,
                "average_trust_level": 0
            }


# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()