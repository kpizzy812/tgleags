"""
CLI интерфейс для управления Telegram AI Companion
"""
import asyncio
import sys
import signal
from typing import Optional
import click
from loguru import logger

# Добавляем путь к модулям
sys.path.append('.')

from src.config.settings import settings, character_settings
from src.core.message_monitor import MessageMonitor
from src.database.database import db_manager
from src.utils.helpers import setup_logging
import json

@cli.command()
def status():
    """Показать расширенный статус приложения"""
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
        
        # Очередь ответов
        if status.get('response_queue_size', 0) > 0:
            click.echo(f"\n⏰ Очередь ответов:")
            queue_info = status.get('queue_info', [])
            for item in queue_info[:3]:  # Показываем первые 3
                time_to_send = item.get('time_to_send_seconds', 0)
                if time_to_send > 0:
                    click.echo(f"   Чат {item['chat_id']}: через {time_to_send:.0f}с - {item['message_preview']}")
                else:
                    click.echo(f"   Чат {item['chat_id']}: готов к отправке - {item['message_preview']}")
    
    asyncio.run(_status())


@cli.command()
@click.option('--chat-id', '-c', type=int, help='ID чата для статистики')
def stats(chat_id: int):
    """Показать статистику диалогов"""
    async def _stats():
        if chat_id:
            # Статистика конкретного чата
            stats = db_manager.get_conversation_stats(chat_id)
            if not stats['total_messages']:
                click.echo(f"📭 Нет сообщений в чате {chat_id}")
                return
            
            click.echo(f"\n📊 Статистика чата {chat_id}:")
            click.echo(f"   Всего сообщений: {stats['total_messages']}")
            click.echo(f"   От пользователя: {stats['user_messages']}")
            click.echo(f"   От ИИ: {stats['ai_messages']}")
            click.echo(f"   Процент ответов: {stats['response_rate']:.1%}")
            
            if stats['conversation_duration_seconds']:
                duration_hours = stats['conversation_duration_seconds'] / 3600
                click.echo(f"   Длительность диалога: {duration_hours:.1f} часов")
                click.echo(f"   Сообщений в день: {stats['messages_per_day']:.1f}")
            
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
                stats = db_manager.get_conversation_stats(chat.id)
                total_messages += stats['total_messages']
                total_ai_messages += stats['ai_messages']
            
            click.echo(f"   Всего сообщений: {total_messages}")
            click.echo(f"   Ответов ИИ: {total_ai_messages}")
            
            if active_chats:
                click.echo(f"\n💬 Топ активных чатов:")
                for chat in active_chats[:5]:
                    stats = db_manager.get_conversation_stats(chat.id)
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
def unanswered():
    """Показать чаты с неотвеченными сообщениями"""
    unanswered_chats = db_manager.get_unanswered_chats(hours_threshold=2)
    
    if not unanswered_chats:
        click.echo("✅ Нет чатов с неотвеченными сообщениями")
        return
    
    click.echo(f"\n⚠️ Чаты с неотвеченными сообщениями ({len(unanswered_chats)}):")
    click.echo("-" * 60)
    
    for chat in unanswered_chats:
        name = chat.first_name or "Без имени"
        username = f"@{chat.username}" if chat.username else ""
        
        # Получаем последнее сообщение
        messages = db_manager.get_chat_messages(chat.id, limit=1)
        if messages:
            last_msg = messages[-1]
            time_ago = (datetime.utcnow() - last_msg.created_at).total_seconds() / 3600
            click.echo(f"👤 {name} {username} (ID: {chat.id})")
            click.echo(f"   Последнее сообщение {time_ago:.1f}ч назад: {last_msg.text[:50]}...")
            click.echo()


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


if __name__ == "__main__":
    cli()