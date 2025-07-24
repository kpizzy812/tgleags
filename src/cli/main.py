"""
CLI интерфейс для управления Telegram AI Companion
"""
import asyncio
import sys
import signal
import json
from typing import Optional
from datetime import datetime
import click
from loguru import logger

# Добавляем путь к модулям
sys.path.append('.')

from src.config.settings import settings, character_settings
from src.core.message_monitor import MessageMonitor
from src.database.database import db_manager
from src.utils.helpers import setup_logging

import json
from src.database.models import Chat, DialogueAnalytics, PersonFact
from sqlalchemy.orm import Session
from sqlalchemy import and_


class TelegramAIApp:
    """Основное приложение"""
    
    def __init__(self):
        self.monitor: Optional[MessageMonitor] = None
        self.is_running = False
        
        # Настраиваем обработчик сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        logger.info("Получен сигнал завершения, останавливаем приложение...")
        self.is_running = False
        if self.monitor:
            asyncio.create_task(self.monitor.stop())
    
    async def start_monitoring(self):
        """Запуск мониторинга сообщений"""
        try:
            self.monitor = MessageMonitor()
            self.is_running = True
            
            logger.info("🚀 Запуск Telegram AI Companion...")
            logger.info(f"📱 Персонаж: {character_settings.name}, {character_settings.age} лет")
            logger.info(f"🔄 Интервал мониторинга: {settings.monitor_interval} секунд")
            
            await self.monitor.start()
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
        except Exception as e:
            logger.error(f"Ошибка запуска мониторинга: {e}")
        finally:
            if self.monitor:
                await self.monitor.stop()
            logger.info("👋 Приложение остановлено")
    
    async def send_message(self, user_id: int, message: str):
        """Отправка сообщения пользователю"""
        if not self.monitor:
            self.monitor = MessageMonitor()
            if not await self.monitor.telegram_client.initialize():
                logger.error("Не удалось инициализировать клиент")
                return False
            if not await self.monitor.telegram_client.connect():
                logger.error("Не удалось подключиться к Telegram")
                return False
        
        success = await self.monitor.send_manual_message(user_id, message)
        if success:
            logger.info(f"✅ Сообщение отправлено пользователю {user_id}")
        else:
            logger.error(f"❌ Не удалось отправить сообщение пользователю {user_id}")
        
        return success
    
    async def get_status(self):
        """Получить статус приложения"""
        if not self.monitor:
            return {
                'status': 'stopped',
                'monitoring': False,
                'telegram_connected': False
            }
        
        status = self.monitor.get_status()
        # Добавляем информацию об очереди
        status['queue_info'] = self.monitor.get_queue_info()
        return status
    
    async def get_dialogs(self):
        """Получить список диалогов"""
        if not self.monitor:
            self.monitor = MessageMonitor()
            if not await self.monitor.telegram_client.initialize():
                return []
            if not await self.monitor.telegram_client.connect():
                return []
        
        return await self.monitor.get_dialogs()


# Глобальный экземпляр приложения
app = TelegramAIApp()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Telegram AI Companion - автоматизированный чат-бот для Telegram"""
    setup_logging()


@cli.command()
def start():
    """Запустить мониторинг сообщений"""
    click.echo("🤖 Запуск Telegram AI Companion...")
    try:
        asyncio.run(app.start_monitoring())
    except KeyboardInterrupt:
        click.echo("\n👋 Остановка по запросу пользователя")
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}")


@cli.command()
@click.option('--user-id', '-u', type=int, required=True, help='ID пользователя Telegram')
@click.option('--message', '-m', required=True, help='Текст сообщения')
def send(user_id: int, message: str):
    """Отправить сообщение пользователю"""
    async def _send():
        await app.send_message(user_id, message)
    
    asyncio.run(_send())


@cli.command()
def status():
    """Показать статус приложения"""
    async def _status():
        status = await app.get_status()
        
        click.echo("\n📊 Статус Telegram AI Companion:")
        click.echo(f"   Мониторинг: {'🟢 Активен' if status.get('monitoring') else '🔴 Остановлен'}")
        click.echo(f"   Telegram: {'🟢 Подключен' if status.get('telegram_connected') else '🔴 Отключен'}")
        click.echo(f"   Очередь ответов: {status.get('response_queue_size', 0)}")
        click.echo(f"   Активные чаты: {status.get('active_chats', 0)}")
        
        # Статистика Telegram клиента
        telegram_stats = status.get('telegram_stats', {})
        if telegram_stats:
            click.echo(f"\n📱 Telegram статистика:")
            click.echo(f"   Отправлено сообщений: {telegram_stats.get('messages_sent', 0)}")
            click.echo(f"   Успешных запросов: {telegram_stats.get('successful_requests', 0)}")
            click.echo(f"   Ошибок: {telegram_stats.get('failed_requests', 0)}")
            click.echo(f"   Переподключений: {telegram_stats.get('reconnections', 0)}")
    
    asyncio.run(_status())


@cli.command()
def dialogs():
    """Показать список диалогов"""
    async def _dialogs():
        dialogs_list = await app.get_dialogs()
        
        if not dialogs_list:
            click.echo("📭 Нет активных диалогов")
            return
        
        click.echo(f"\n💬 Найдено диалогов: {len(dialogs_list)}")
        click.echo("-" * 80)
        
        for dialog in dialogs_list[:10]:  # Показываем первые 10
            name = dialog.get('name', 'Без имени')
            username = f"@{dialog['username']}" if dialog.get('username') else ""
            unread = dialog.get('unread_count', 0)
            last_msg = dialog.get('last_message', '')
            
            click.echo(f"👤 {name} {username} (ID: {dialog['id']})")
            if unread > 0:
                click.echo(f"   🔴 Непрочитанных: {unread}")
            if last_msg:
                click.echo(f"   💭 Последнее: {last_msg[:50]}...")
            click.echo()
    
    asyncio.run(_dialogs())


@cli.command()
def config():
    """Показать конфигурацию"""
    click.echo("\n⚙️  Конфигурация:")
    click.echo(f"   📱 Телефон: {settings.telegram_phone}")
    click.echo(f"   🤖 OpenAI модель: {settings.openai_model}")
    click.echo(f"   🕐 Интервал мониторинга: {settings.monitor_interval} сек")
    click.echo(f"   📊 Уровень логов: {settings.log_level}")
    click.echo(f"   💾 База данных: {settings.database_url}")
    
    click.echo(f"\n👤 Персонаж:")
    click.echo(f"   Имя: {character_settings.name}")
    click.echo(f"   Возраст: {character_settings.age}")
    click.echo(f"   Профессия: {character_settings.occupation}")
    click.echo(f"   Город: {character_settings.location}")
    click.echo(f"   Интересы: {', '.join(character_settings.interests)}")


@cli.command()
def test():
    """Тестовая команда для проверки подключения"""
    async def _test():
        click.echo("🔧 Тестирование подключения...")
        
        # Тест базы данных
        try:
            chats = db_manager.get_active_chats()
            click.echo(f"✅ База данных: подключена (чатов: {len(chats)})")
        except Exception as e:
            click.echo(f"❌ База данных: {e}")
        
        # Тест Telegram подключения
        try:
            monitor = MessageMonitor()
            if await monitor.telegram_client.initialize():
                if await monitor.telegram_client.connect():
                    click.echo("✅ Telegram: подключение успешно")
                    await monitor.telegram_client.stop_monitoring()
                else:
                    click.echo("❌ Telegram: ошибка подключения")
            else:
                click.echo("❌ Telegram: ошибка инициализации")
        except Exception as e:
            click.echo(f"❌ Telegram: {e}")
        
        # Тест OpenAI
        try:
            from src.core.response_generator import ResponseGenerator
            generator = ResponseGenerator()
            click.echo(f"✅ OpenAI: настроен (модель: {settings.openai_model})")
        except Exception as e:
            click.echo(f"❌ OpenAI: {e}")
    
    asyncio.run(_test())


@cli.command()
@click.option('--chat-id', '-c', type=int, help='ID чата для просмотра')
@click.option('--limit', '-l', default=10, help='Количество сообщений')
def messages(chat_id: int, limit: int):
    """Показать сообщения чата"""
    if not chat_id:
        # Показываем список чатов
        chats = db_manager.get_active_chats()
        if not chats:
            click.echo("📭 Нет активных чатов")
            return
        
        click.echo(f"\n💬 Активные чаты ({len(chats)}):")
        for chat in chats[:10]:
            name = chat.first_name or "Без имени"
            username = f"@{chat.username}" if chat.username else ""
            click.echo(f"   {chat.id}: {name} {username} (User ID: {chat.telegram_user_id})")
        
        click.echo(f"\nИспользуйте: python -m src.cli.main messages -c <chat_id>")
        return
    
    # Показываем сообщения конкретного чата
    messages_list = db_manager.get_chat_messages(chat_id, limit)
    
    if not messages_list:
        click.echo(f"📭 Нет сообщений в чате {chat_id}")
        return
    
    click.echo(f"\n💬 Сообщения чата {chat_id} (последние {len(messages_list)}):")
    click.echo("-" * 80)
    
    for msg in messages_list:
        sender = "🤖 AI" if msg.is_from_ai else "👤 User"
        time_str = msg.created_at.strftime("%H:%M:%S")
        text = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
        click.echo(f"{time_str} {sender}: {text}")


@cli.command()
@click.option('--chat-id', '-c', type=int, help='ID чата для статистики')
def stats(chat_id: int):
    """Показать статистику диалогов"""
    async def _stats():
        if chat_id:
            # Статистика конкретного чата
            stats = db_manager.get_message_statistics(chat_id)
            if not stats['total_messages']:
                click.echo(f"📭 Нет сообщений в чате {chat_id}")
                return
            
            click.echo(f"\n📊 Статистика чата {chat_id}:")
            click.echo(f"   Всего сообщений: {stats['total_messages']}")
            click.echo(f"   От пользователя: {stats['user_messages']}")
            click.echo(f"   От ИИ: {stats['ai_messages']}")
            click.echo(f"   Процент ответов: {stats['response_rate']:.1%}")
            
            # Контекст чата
            context = db_manager.get_chat_context(chat_id)
            if context:
                click.echo(f"\n🎯 Контекст:")
                click.echo(f"   Стадия отношений: {context.relationship_stage}")
                if context.detected_interests:
                    interests = json.loads(context.detected_interests)
                    click.echo(f"   Интересы: {', '.join(interests)}")
        else:
            # Общая статистика
            active_chats = db_manager.get_active_chats()
            click.echo(f"\n📊 Общая статистика:")
            click.echo(f"   Активных чатов: {len(active_chats)}")
            
            total_messages = 0
            total_ai_messages = 0
            for chat in active_chats:
                stats = db_manager.get_message_statistics(chat.id)
                total_messages += stats['total_messages']
                total_ai_messages += stats['ai_messages']
            
            click.echo(f"   Всего сообщений: {total_messages}")
            click.echo(f"   Ответов ИИ: {total_ai_messages}")
            
            if active_chats:
                click.echo(f"\n💬 Топ активных чатов:")
                for chat in active_chats[:5]:
                    stats = db_manager.get_message_statistics(chat.id)
                    name = chat.first_name or "Без имени"
                    click.echo(f"   {name} ({chat.id}): {stats['total_messages']} сообщений")
    
    asyncio.run(_stats())


@cli.command()
def queue():
    """Показать очередь ответов"""
    async def _queue():
        status = await app.get_status()
        queue_size = status.get('response_queue_size', 0)
        
        if queue_size == 0:
            click.echo("📭 Очередь ответов пуста")
            return
        
        click.echo(f"\n⏰ Очередь ответов ({queue_size} элементов):")
        click.echo("-" * 80)
        
        queue_info = status.get('queue_info', [])
        for i, item in enumerate(queue_info, 1):
            time_to_send = item.get('time_to_send_seconds', 0)
            delay_reason = item.get('delay_reason', 'unknown')
            
            if time_to_send > 0:
                if time_to_send < 60:
                    time_str = f"{time_to_send:.0f}с"
                else:
                    time_str = f"{time_to_send/60:.1f}мин"
                status_str = f"через {time_str}"
            else:
                status_str = "готов к отправке"
            
            click.echo(f"{i}. Чат {item['chat_id']} - {status_str}")
            click.echo(f"   Причина задержки: {delay_reason}")
            click.echo(f"   Сообщение: {item['message_preview']}")
            click.echo()
    
    asyncio.run(_queue())


@cli.command()
@click.option('--days', '-d', default=7, help='Количество дней для очистки')
def cleanup(days: int):
    """Очистка старых сообщений"""
    click.echo(f"🧹 Очистка сообщений старше {days} дней...")
    
    deleted_count = db_manager.cleanup_old_messages(days_to_keep=days)
    
    if deleted_count > 0:
        click.echo(f"✅ Удалено {deleted_count} старых сообщений")
    else:
        click.echo("📭 Нет сообщений для удаления")


@cli.command()
@click.option('--chat-id', '-c', type=int, help='ID чата для анализа')
def analyze(chat_id: int):
    """Показать детальный анализ диалога"""
    if not chat_id:
        click.echo("❌ Необходимо указать chat_id: -c CHAT_ID")
        return

    try:
        # Получаем аналитику диалога
        analytics = db_manager.get_dialogue_analytics(chat_id)

        if not analytics:
            click.echo(f"📭 Нет аналитики для чата {chat_id}")
            return

        click.echo(f"\n🔍 Детальный анализ диалога {chat_id}:")
        click.echo("-" * 60)

        # Основные метрики
        click.echo(f"📊 Общий скор перспективности: {analytics.prospect_score}/100")
        click.echo(f"📈 Текущий этап: {analytics.current_stage}")
        click.echo(f"📅 Дней общения: {analytics.dialogue_duration_days}")
        click.echo(f"💬 Всего сообщений: {analytics.total_messages}")

        # Финансовые метрики
        click.echo(f"\n💰 Финансовый анализ:")
        click.echo(f"   Финансовый скор: {analytics.financial_score}/10")
        click.echo(f"   Готовность: {analytics.financial_readiness}")
        click.echo(f"   Жалобы на деньги: {analytics.money_complaints_count}")

        if analytics.expensive_desires:
            try:
                desires = json.loads(analytics.expensive_desires)
                click.echo(f"   Дорогие желания: {', '.join(desires)}")
            except:
                pass

        # Эмоциональные метрики
        click.echo(f"\n💝 Эмоциональный анализ:")
        click.echo(f"   Уровень доверия: {analytics.trust_level}/10")
        click.echo(f"   Эмоциональная связь: {analytics.emotional_connection}/10")

        # Результат
        click.echo(f"\n🎯 Результат:")
        click.echo(f"   Статус: {analytics.dialogue_outcome or 'ongoing'}")
        if analytics.failure_reason:
            click.echo(f"   Причина неудачи: {analytics.failure_reason}")

        click.echo(f"   Предложение работы: {'✅' if analytics.work_offer_made else '❌'}")
        click.echo(f"   Принято: {'✅' if analytics.work_offer_accepted else '❌'}")

        # Факты о собеседнице
        facts = db_manager.get_person_facts(chat_id)
        if facts:
            click.echo(f"\n📝 Известные факты о ней ({len(facts)}):")
            fact_groups = {}
            for fact in facts[:10]:
                if fact.fact_type not in fact_groups:
                    fact_groups[fact.fact_type] = []
                fact_groups[fact.fact_type].append(f"{fact.fact_value} ({fact.confidence:.1f})")

            for fact_type, values in fact_groups.items():
                click.echo(f"   {fact_type}: {', '.join(values)}")

    except Exception as e:
        click.echo(f"❌ Ошибка анализа: {e}")


@cli.command()
def analytics():
    """Показать общую аналитику по всем диалогам"""
    try:
        summary = db_manager.get_analytics_summary()

        if not summary.get('total_chats'):
            click.echo("📭 Нет данных для аналитики")
            return

        click.echo("\n📊 Общая аналитика диалогов:")
        click.echo("=" * 50)

        click.echo(f"📈 Всего диалогов: {summary['total_chats']}")
        click.echo(f"🎯 Средний скор перспективности: {summary['average_prospect_score']}/100")
        click.echo(f"🤝 Средний уровень доверия: {summary['average_trust_level']}/10")

        # Распределение по этапам
        stage_dist = summary.get('stage_distribution', {})
        if stage_dist:
            click.echo(f"\n📋 Распределение по этапам:")
            for stage, count in stage_dist.items():
                percentage = (count / summary['total_chats']) * 100
                click.echo(f"   {stage}: {count} ({percentage:.1f}%)")

        # Результаты диалогов
        outcome_dist = summary.get('outcome_distribution', {})
        if outcome_dist:
            click.echo(f"\n🎯 Результаты диалогов:")
            for outcome, count in outcome_dist.items():
                if outcome:  # Пропускаем None
                    percentage = (count / summary['total_chats']) * 100
                    click.echo(f"   {outcome}: {count} ({percentage:.1f}%)")

    except Exception as e:
        click.echo(f"❌ Ошибка получения аналитики: {e}")


@cli.command()
@click.option('--stage', '-s', help='Фильтр по этапу (initiation/retention/diagnosis/proposal)')
@click.option('--limit', '-l', default=10, help='Количество чатов для показа')
def prospects(stage: str, limit: int):
    """Показать лучшие перспективы по скору"""
    try:
        with db_manager.get_session() as session:
            query = session.query(DialogueAnalytics).join(Chat)

            # Фильтрация по этапу
            if stage:
                query = query.filter(DialogueAnalytics.current_stage == stage)

            # Только активные диалоги
            query = query.filter(Chat.is_active == True)

            # Сортировка по скору
            prospects = query.order_by(DialogueAnalytics.prospect_score.desc()).limit(limit).all()

            if not prospects:
                click.echo(f"📭 Нет перспективных диалогов" + (f" на этапе {stage}" if stage else ""))
                return

            click.echo(f"\n🎯 Топ {len(prospects)} перспективных диалогов:")
            click.echo("-" * 80)

            for i, analytics in enumerate(prospects, 1):
                chat = analytics.chat
                name = chat.first_name or "Без имени"

                click.echo(f"{i}. {name} (ID: {chat.id}) - Скор: {analytics.prospect_score}/100")
                click.echo(f"   Этап: {analytics.current_stage} | "
                           f"Доверие: {analytics.trust_level}/10 | "
                           f"Финансы: {analytics.financial_readiness}")
                click.echo(f"   Дней: {analytics.dialogue_duration_days} | "
                           f"Сообщений: {analytics.total_messages}")
                click.echo()

    except Exception as e:
        click.echo(f"❌ Ошибка получения перспектив: {e}")


@cli.command()
@click.option('--chat-id', '-c', type=int, help='ID чата')
def facts(chat_id: int):
    """Показать факты о собеседнице"""
    if not chat_id:
        click.echo("❌ Необходимо указать chat_id: -c CHAT_ID")
        return

    try:
        facts_list = db_manager.get_person_facts(chat_id)

        if not facts_list:
            click.echo(f"📭 Нет фактов о собеседнице в чате {chat_id}")
            return

        # Получаем имя чата
        chat = db_manager.get_session().query(Chat).filter(Chat.id == chat_id).first()
        name = chat.first_name if chat else "Неизвестная"

        click.echo(f"\n📝 Факты о {name} (Chat ID: {chat_id}):")
        click.echo("-" * 60)

        # Группируем факты по типам
        fact_groups = {}
        for fact in facts_list:
            if fact.fact_type not in fact_groups:
                fact_groups[fact.fact_type] = []
            fact_groups[fact.fact_type].append(fact)

        for fact_type, facts in fact_groups.items():
            click.echo(f"\n🏷️  {fact_type.upper()}:")
            for fact in facts:
                confidence_icon = "🟢" if fact.confidence >= 0.8 else "🟡" if fact.confidence >= 0.6 else "🔴"
                referenced = f" (использовано {fact.times_referenced}x)" if fact.times_referenced > 0 else ""
                click.echo(f"   {confidence_icon} {fact.fact_value}{referenced}")
                click.echo(f"      Уверенность: {fact.confidence:.1f} | "
                           f"Впервые: {fact.first_mentioned.strftime('%d.%m %H:%M')}")

    except Exception as e:
        click.echo(f"❌ Ошибка получения фактов: {e}")


@cli.command()
def failures():
    """Анализ неудачных диалогов для обучения"""
    try:
        with db_manager.get_session() as session:
            failed_dialogs = session.query(DialogueAnalytics).filter(
                DialogueAnalytics.dialogue_outcome == "failure"
            ).all()

            if not failed_dialogs:
                click.echo("✅ Нет неудачных диалогов для анализа")
                return

            click.echo(f"\n❌ Анализ {len(failed_dialogs)} неудачных диалогов:")
            click.echo("=" * 60)

            # Группируем по причинам неудач
            failure_reasons = {}
            for dialog in failed_dialogs:
                reason = dialog.failure_reason or "unknown"
                if reason not in failure_reasons:
                    failure_reasons[reason] = []
                failure_reasons[reason].append(dialog)

            for reason, dialogs in failure_reasons.items():
                click.echo(f"\n🚨 {reason} ({len(dialogs)} случаев):")

                # Средние метрики для этой группы
                avg_prospect = sum(d.prospect_score for d in dialogs) / len(dialogs)
                avg_trust = sum(d.trust_level for d in dialogs) / len(dialogs)
                avg_days = sum(d.dialogue_duration_days for d in dialogs) / len(dialogs)

                click.echo(f"   📊 Средние показатели:")
                click.echo(f"      Скор перспективности: {avg_prospect:.1f}/100")
                click.echo(f"      Уровень доверия: {avg_trust:.1f}/10")
                click.echo(f"      Продолжительность: {avg_days:.1f} дней")

                # Показываем несколько примеров
                click.echo(f"   📋 Примеры:")
                for dialog in dialogs[:3]:
                    chat = dialog.chat
                    name = chat.first_name or "Без имени"
                    click.echo(f"      • {name} (ID: {chat.id}) - {dialog.current_stage} этап")

    except Exception as e:
        click.echo(f"❌ Ошибка анализа неудач: {e}")


# ОБНОВИТЬ команду status для показа аналитики:
@cli.command()
def status():
    """Показать расширенный статус приложения"""

    async def _status():
        status = await app.get_status()

        click.echo("\n📊 Статус Telegram AI Companion:")
        click.echo("=" * 50)
        click.echo(f"   Мониторинг: {'🟢 Активен' if status.get('monitoring') else '🔴 Остановлен'}")
        click.echo(f"   Telegram: {'🟢 Подключен' if status.get('telegram_connected') else '🔴 Отключен'}")
        click.echo(f"   Очередь ответов: {status.get('response_queue_size', 0)}")
        click.echo(f"   Активные чаты: {status.get('active_chats', 0)}")

        # Telegram статистика
        telegram_stats = status.get('telegram_stats', {})
        if telegram_stats:
            click.echo(f"\n📱 Telegram статистика:")
            click.echo(f"   Отправлено сообщений: {telegram_stats.get('messages_sent', 0)}")
            click.echo(f"   Успешных запросов: {telegram_stats.get('successful_requests', 0)}")
            click.echo(f"   Ошибок: {telegram_stats.get('failed_requests', 0)}")

        # Новая аналитика диалогов
        analytics_summary = db_manager.get_analytics_summary()
        if analytics_summary.get('total_chats', 0) > 0:
            click.echo(f"\n🎯 Аналитика диалогов:")
            click.echo(f"   Всего диалогов: {analytics_summary['total_chats']}")
            click.echo(f"   Средний скор: {analytics_summary['average_prospect_score']}/100")
            click.echo(f"   Средний уровень доверия: {analytics_summary['average_trust_level']}/10")

            # Топ этапы
            stage_dist = analytics_summary.get('stage_distribution', {})
            if stage_dist:
                top_stage = max(stage_dist.keys(), key=lambda k: stage_dist[k])
                click.echo(f"   Популярный этап: {top_stage} ({stage_dist[top_stage]} диалогов)")

    asyncio.run(_status())

if __name__ == "__main__":
    cli()