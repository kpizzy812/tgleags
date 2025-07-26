"""
Команды для работы с чатами и сообщениями
"""
import asyncio
import click
from loguru import logger

from ..database.database import db_manager


class ChatCommands:
    """Команды для работы с чатами"""

    @staticmethod
    @click.command()
    @click.option('--user-id', '-u', type=int, required=True, help='ID пользователя Telegram')
    @click.option('--message', '-m', required=True, help='Текст сообщения')
    def send(user_id: int, message: str):
        """📤 Отправить сообщение пользователю"""

        async def _send():
            from .main import app
            await app.send_message(user_id, message)

        asyncio.run(_send())

    @staticmethod
    @click.command()
    @click.option('--limit', '-l', default=10, help='Количество диалогов')
    def dialogs(limit: int):
        """💬 Показать список диалогов"""

        async def _dialogs():
            from .main import app
            dialogs_list = await app.get_dialogs()

            if not dialogs_list:
                click.echo("📭 Нет активных диалогов")
                return

            click.echo(f"\n💬 Найдено диалогов: {len(dialogs_list)}")
            click.echo("-" * 70)

            for i, dialog in enumerate(dialogs_list[:limit], 1):
                name = dialog.get('name', 'Без имени')
                username = f"@{dialog['username']}" if dialog.get('username') else ""
                unread = dialog.get('unread_count', 0)
                last_msg = dialog.get('last_message', '')

                # Иконка статуса
                status_icon = "🔴" if unread > 0 else "⚪"

                click.echo(f"{status_icon} {i}. {name} {username} (ID: {dialog['id']})")

                if unread > 0:
                    click.echo(f"     📨 Непрочитанных: {unread}")

                if last_msg:
                    click.echo(f"     💭 Последнее: {last_msg[:50]}...")

                click.echo()

        asyncio.run(_dialogs())

    @staticmethod
    @click.command()
    @click.option('--chat-id', '-c', type=int, help='ID чата для просмотра')
    @click.option('--limit', '-l', default=20, help='Количество сообщений')
    def messages(chat_id: int, limit: int):
        """📜 Показать сообщения чата"""
        if not chat_id:
            # Показываем список чатов с подсказкой
            chats = db_manager.get_active_chats()
            if not chats:
                click.echo("📭 Нет активных чатов в базе данных")
                return

            click.echo(f"\n💬 Активные чаты в базе данных ({len(chats)}):")
            click.echo("-" * 70)

            for chat in chats[:15]:  # Показываем топ 15
                name = chat.first_name or "Без имени"
                username = f"@{chat.username}" if chat.username else ""

                # Получаем количество сообщений
                stats = db_manager.get_message_statistics(chat.id)
                total_msgs = stats['total_messages']

                # Получаем факты для краткого статуса
                facts = db_manager.get_person_facts(chat.id)
                status_parts = []

                if any(f.fact_type == "job" for f in facts):
                    status_parts.append("💼 работа")
                if any(f.fact_type == "financial_complaint" for f in facts):
                    status_parts.append("💰 жалобы")
                if any(f.fact_type == "expensive_dream" for f in facts):
                    status_parts.append("✨ мечты")

                status = " | ".join(status_parts) if status_parts else "обычное общение"

                click.echo(f"   {chat.id}: {name} {username}")
                click.echo(f"        User ID: {chat.telegram_user_id} | {total_msgs} сообщений")
                click.echo(f"        Статус: {status}")
                click.echo()

            click.echo(f"💡 Для просмотра сообщений: telegram-ai messages -c <chat_id>")
            return

        # Показываем сообщения конкретного чата
        messages_list = db_manager.get_chat_messages(chat_id, limit)

        if not messages_list:
            click.echo(f"📭 Нет сообщений в чате {chat_id}")
            return

        # Получаем информацию о чате
        chat = db_manager.get_chat_by_id(chat_id)
        chat_name = chat.first_name if chat else f"Чат {chat_id}"

        click.echo(f"\n💬 Сообщения: {chat_name} (последние {len(messages_list)}):")
        click.echo("-" * 70)

        for msg in messages_list:
            # Иконки отправителей
            sender_icon = "🤖" if msg.is_from_ai else "👤"
            sender_name = "Стас" if msg.is_from_ai else chat_name

            # Форматирование времени
            time_str = msg.created_at.strftime("%d.%m %H:%M")

            # Текст сообщения (обрезаем если длинный)
            text = msg.text or ""
            if len(text) > 100:
                text = text[:100] + "..."

            click.echo(f"{time_str} {sender_icon} {sender_name}: {text}")


# Создаем экземпляр для экспорта команд
chat_commands = ChatCommands()