"""
Простой CLI для Telegram AI Companion - максимально человечный
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

# Импортируем команды из модулей
from .chat_commands import chat_commands
from .stats_commands import stats_commands


class SimpleApp:
    """Простое приложение без переусложнения"""

    def __init__(self):
        self.monitor: Optional[MessageMonitor] = None
        self.is_running = False

        # Обработчик сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Корректное завершение"""
        logger.info("Получен сигнал завершения...")
        self.is_running = False
        if self.monitor:
            asyncio.create_task(self.monitor.stop())

    async def start_monitoring(self):
        """Запуск мониторинга"""
        try:
            self.monitor = MessageMonitor()
            self.is_running = True

            logger.info("🚀 Запуск Telegram AI Companion...")
            logger.info(f"👤 Персонаж: {character_settings.name}, {character_settings.age} лет")
            logger.info(f"🔄 Интервал: {settings.monitor_interval} секунд")

            await self.monitor.start()

        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
        except Exception as e:
            logger.error(f"Ошибка запуска: {e}")
        finally:
            if self.monitor:
                await self.monitor.stop()
            logger.info("👋 Приложение остановлено")

    async def send_message(self, user_id: int, message: str):
        """Отправка сообщения"""
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
        """Статус приложения"""
        if not self.monitor:
            return {
                'status': 'stopped',
                'monitoring': False,
                'telegram_connected': False
            }

        status = self.monitor.get_status()
        status['queue_info'] = self.monitor.get_queue_info()
        return status

    async def get_dialogs(self):
        """Список диалогов"""
        if not self.monitor:
            self.monitor = MessageMonitor()
            if not await self.monitor.telegram_client.initialize():
                return []
            if not await self.monitor.telegram_client.connect():
                return []

        return await self.monitor.get_dialogs()


# Глобальный экземпляр
app = SimpleApp()


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Telegram AI Companion - простой и естественный чат-бот"""
    setup_logging()


# =============================================================================
# ОСНОВНЫЕ КОМАНДЫ
# =============================================================================

@cli.command()
def start():
    """🚀 Запустить мониторинг сообщений"""
    click.echo("🤖 Запуск Telegram AI Companion...")
    try:
        asyncio.run(app.start_monitoring())
    except KeyboardInterrupt:
        click.echo("\n👋 Остановка по запросу пользователя")
    except Exception as e:
        click.echo(f"❌ Ошибка: {e}")


@cli.command()
def status():
    """📊 Показать статус приложения"""
    async def _status():
        status = await app.get_status()

        click.echo("\n📊 Статус Telegram AI Companion:")
        click.echo("=" * 50)

        # Основной статус
        monitoring = status.get('monitoring', False)
        telegram = status.get('telegram_connected', False)
        queue_size = status.get('response_queue_size', 0)
        active_chats = status.get('active_chats', 0)

        click.echo(f"   Мониторинг: {'🟢 Работает' if monitoring else '🔴 Остановлен'}")
        click.echo(f"   Telegram: {'🟢 Подключен' if telegram else '🔴 Отключен'}")
        click.echo(f"   Очередь ответов: {queue_size}")
        click.echo(f"   Активные чаты: {active_chats}")

        # Статистика Telegram
        telegram_stats = status.get('telegram_stats', {})
        if telegram_stats:
            click.echo(f"\n📱 Статистика Telegram:")
            click.echo(f"   Отправлено сообщений: {telegram_stats.get('messages_sent', 0)}")
            click.echo(f"   Успешных запросов: {telegram_stats.get('successful_requests', 0)}")
            click.echo(f"   Ошибок: {telegram_stats.get('failed_requests', 0)}")

    asyncio.run(_status())


@cli.command()
def config():
    """⚙️ Показать конфигурацию"""
    click.echo("\n⚙️ Конфигурация:")
    click.echo(f"   📱 Телефон: {settings.telegram_phone}")
    click.echo(f"   🤖 OpenAI модель: {settings.openai_model}")
    click.echo(f"   🕐 Интервал мониторинга: {settings.monitor_interval} сек")
    click.echo(f"   📊 Уровень логов: {settings.log_level}")

    click.echo(f"\n👤 Персонаж:")
    click.echo(f"   Имя: {character_settings.name}")
    click.echo(f"   Возраст: {character_settings.age}")
    click.echo(f"   Профессия: {character_settings.occupation}")
    click.echo(f"   Город: {character_settings.location}")
    click.echo(f"   Интересы: {', '.join(character_settings.interests[:3])}...")


@cli.command()
def test():
    """🔧 Тест подключений"""
    async def _test():
        click.echo("🔧 Тестирование подключений...")

        # Тест базы данных
        try:
            chats = db_manager.get_active_chats()
            click.echo(f"✅ База данных: подключена ({len(chats)} чатов)")
        except Exception as e:
            click.echo(f"❌ База данных: {e}")

        # Тест Telegram
        try:
            monitor = MessageMonitor()
            if await monitor.telegram_client.initialize():
                if await monitor.telegram_client.connect():
                    me = await monitor.telegram_client.client.get_me()
                    if me:
                        click.echo(f"✅ Telegram: подключен как {me.first_name}")
                    else:
                        click.echo("⚠️ Telegram: подключен, но не удалось получить информацию")
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

        click.echo("\n🎯 Результат:")
        click.echo("Если все тесты прошли успешно - можно запускать мониторинг")

    asyncio.run(_test())


@cli.command()
def queue():
    """⏰ Показать очередь ответов"""
    async def _queue():
        status = await app.get_status()
        queue_size = status.get('response_queue_size', 0)

        if queue_size == 0:
            click.echo("📭 Очередь ответов пуста")
            return

        click.echo(f"\n⏰ Очередь ответов ({queue_size} элементов):")
        click.echo("-" * 60)

        queue_info = status.get('queue_info', [])
        for i, item in enumerate(queue_info, 1):
            time_to_send = item.get('time_to_send_seconds', 0)

            if time_to_send > 0:
                if time_to_send < 60:
                    time_str = f"{time_to_send:.0f}с"
                else:
                    time_str = f"{time_to_send/60:.1f}мин"
                status_str = f"через {time_str}"
            else:
                status_str = "готов к отправке"

            click.echo(f"{i}. Чат {item['chat_id']} - {status_str}")
            click.echo(f"   {item['message_preview']}")

    asyncio.run(_queue())


# =============================================================================
# ПОДКЛЮЧАЕМ КОМАНДЫ ИЗ МОДУЛЕЙ
# =============================================================================

# Добавляем команды для работы с чатами
cli.add_command(chat_commands.send)
cli.add_command(chat_commands.dialogs)
cli.add_command(chat_commands.messages)
cli.add_command(stats_commands.dev)

# Добавляем команды статистики
cli.add_command(stats_commands.stats)
cli.add_command(stats_commands.facts)
cli.add_command(stats_commands.opportunities)


if __name__ == "__main__":
    cli()