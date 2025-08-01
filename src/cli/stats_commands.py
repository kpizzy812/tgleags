"""
Простые команды статистики - без переусложнения
"""
import click
from loguru import logger

from ..database.database import db_manager


class StatsCommands:
    """Простые команды статистики"""

    @staticmethod
    @click.command()
    @click.option('--detailed', '-d', is_flag=True, help='Подробная статистика')
    def stats(detailed: bool):
        """📊 Простая статистика диалогов"""
        try:
            active_chats = db_manager.get_active_chats()

            if not active_chats:
                click.echo("📭 Нет активных диалогов")
                return

            click.echo(f"\n📊 Статистика диалогов:")
            click.echo("=" * 50)
            click.echo(f"   Всего активных диалогов: {len(active_chats)}")

            # Подсчитываем общие метрики
            total_messages = 0
            total_ai_messages = 0
            chats_with_facts = 0

            for chat in active_chats:
                stats = db_manager.get_message_statistics(chat.id)
                total_messages += stats['total_messages']
                total_ai_messages += stats['ai_messages']

                facts = db_manager.get_person_facts(chat.id)
                if facts:
                    chats_with_facts += 1

            click.echo(f"   Всего сообщений: {total_messages}")
            click.echo(f"   Ответов от ИИ: {total_ai_messages}")
            click.echo(f"   Диалогов с фактами: {chats_with_facts}")

            if total_messages > 0:
                response_rate = (total_ai_messages / (total_messages - total_ai_messages)) * 100
                click.echo(f"   Процент ответов: {response_rate:.1f}%")

            # Подробная статистика если запрошена
            if detailed and active_chats:
                click.echo(f"\n💬 Топ активных диалогов:")
                click.echo("-" * 50)

                # Сортируем по количеству сообщений
                chat_stats = []
                for chat in active_chats:
                    stats = db_manager.get_message_statistics(chat.id)
                    chat_stats.append((chat, stats['total_messages']))

                chat_stats.sort(key=lambda x: x[1], reverse=True)

                for chat, msg_count in chat_stats[:10]:
                    name = chat.first_name or "Без имени"

                    # Получаем простой статус
                    facts = db_manager.get_person_facts(chat.id)
                    status_indicators = []

                    if any(f.fact_type == "financial_complaint" for f in facts):
                        status_indicators.append("💰")
                    if any(f.fact_type == "expensive_dream" for f in facts):
                        status_indicators.append("✨")
                    if any(f.fact_type == "job" for f in facts):
                        status_indicators.append("💼")

                    status = "".join(status_indicators) if status_indicators else "💬"

                    click.echo(f"   {status} {name} ({chat.id}): {msg_count} сообщений")

        except Exception as e:
            click.echo(f"❌ Ошибка получения статистики: {e}")

    @staticmethod
    @click.command()
    @click.option('--chat-id', '-c', type=int, help='ID чата')
    def facts(chat_id: int):
        """📝 Показать факты о собеседницах"""
        if not chat_id:
            # Показываем общую сводку по всем чатам
            active_chats = db_manager.get_active_chats()

            if not active_chats:
                click.echo("📭 Нет активных чатов")
                return

            click.echo(f"\n📝 Факты по всем диалогам:")
            click.echo("=" * 60)

            total_facts = 0
            chats_with_facts = 0

            for chat in active_chats:
                facts = db_manager.get_person_facts(chat.id)
                if not facts:
                    continue

                chats_with_facts += 1
                total_facts += len(facts)

                name = chat.first_name or "Без имени"

                # Группируем факты по типам
                work_facts = [f for f in facts if f.fact_type == "job"]
                money_facts = [f for f in facts if f.fact_type == "financial_complaint"]
                dream_facts = [f for f in facts if f.fact_type == "expensive_dream"]

                click.echo(f"\n👤 {name} (ID: {chat.id}):")

                if work_facts:
                    click.echo(f"   💼 Работа: {work_facts[0].fact_value}")

                if money_facts:
                    click.echo(f"   💰 Жалобы: {', '.join([f.fact_value for f in money_facts])}")

                if dream_facts:
                    click.echo(f"   ✨ Мечты: {', '.join([f.fact_value for f in dream_facts])}")

            click.echo(f"\n📊 Итого:")
            click.echo(f"   Диалогов с фактами: {chats_with_facts}")
            click.echo(f"   Всего фактов: {total_facts}")
            click.echo(f"\n💡 Для подробностей: telegram-ai facts -c <chat_id>")
            return

        # Показываем факты конкретного чата
        facts_list = db_manager.get_person_facts(chat_id)

        if not facts_list:
            click.echo(f"📭 Нет фактов о собеседнице в чате {chat_id}")
            return

        # Получаем имя чата
        chat = db_manager.get_chat_by_id(chat_id)
        name = chat.first_name if chat else "Неизвестная"

        click.echo(f"\n📝 Что мы знаем о {name} (Chat ID: {chat_id}):")
        click.echo("-" * 60)

        # Группируем факты по типам
        fact_groups = {
            "job": "💼 Работа",
            "financial_complaint": "💰 Жалобы на деньги",
            "expensive_dream": "✨ Дорогие мечты",
            "other": "📄 Другое"
        }

        for fact_type, title in fact_groups.items():
            type_facts = [f for f in facts_list if f.fact_type == fact_type]
            if type_facts:
                click.echo(f"\n{title}:")
                for fact in type_facts:
                    confidence_icon = "🟢" if fact.confidence >= 0.8 else "🟡"
                    click.echo(f"   {confidence_icon} {fact.fact_value}")

    @staticmethod
    @click.command()
    @click.option('--show-all', '-a', is_flag=True, help='Показать все диалоги')
    def opportunities(show_all: bool):
        """🎯 Показать возможности для предложения работы"""
        try:
            active_chats = db_manager.get_active_chats()
            opportunities_found = False

            click.echo(f"\n🎯 Анализ возможностей для предложения работы:")
            click.echo("=" * 60)

            high_opportunities = []
            medium_opportunities = []
            low_opportunities = []

            for chat in active_chats:
                facts = db_manager.get_person_facts(chat.id)

                money_complaints = [f for f in facts if f.fact_type == "financial_complaint"]
                dreams = [f for f in facts if f.fact_type == "expensive_dream"]
                work_facts = [f for f in facts if f.fact_type == "job"]

                # Считаем сообщения для понимания стадии отношений
                stats = db_manager.get_message_statistics(chat.id)
                message_count = stats['total_messages']

                name = chat.first_name or "Без имени"

                # Определяем уровень возможности
                if money_complaints and dreams and message_count >= 30:
                    # Высокая возможность
                    high_opportunities.append((chat, money_complaints, dreams, work_facts, message_count))
                    opportunities_found = True

                elif (money_complaints or dreams) and message_count >= 20:
                    # Средняя возможность
                    medium_opportunities.append((chat, money_complaints, dreams, work_facts, message_count))
                    opportunities_found = True

                elif message_count >= 10 and show_all:
                    # Низкая возможность (показываем только с флагом)
                    low_opportunities.append((chat, money_complaints, dreams, work_facts, message_count))

            # Показываем высокие возможности
            if high_opportunities:
                click.echo(f"\n🔥 ВЫСОКИЕ ВОЗМОЖНОСТИ (готовы к предложению):")
                for chat, complaints, dreams, work, msg_count in high_opportunities:
                    name = chat.first_name or "Без имени"
                    click.echo(f"\n👤 {name} (ID: {chat.id}) - 🎯 ОТЛИЧНАЯ ВОЗМОЖНОСТЬ")
                    click.echo(f"   📊 Сообщений: {msg_count} (достаточно для предложения)")

                    if work:
                        click.echo(f"   💼 Работа: {work[0].fact_value}")
                    if complaints:
                        click.echo(f"   💰 Жалобы: {', '.join([f.fact_value for f in complaints])}")
                    if dreams:
                        click.echo(f"   ✨ Мечты: {', '.join([f.fact_value for f in dreams])}")

                    click.echo(f"   💡 Рекомендация: Можно предлагать работу в крипте!")

            # Показываем средние возможности
            if medium_opportunities:
                click.echo(f"\n⚡ СРЕДНИЕ ВОЗМОЖНОСТИ (нужно еще поработать):")
                for chat, complaints, dreams, work, msg_count in medium_opportunities:
                    name = chat.first_name or "Без имени"
                    click.echo(f"\n👤 {name} (ID: {chat.id}) - ⚡ Перспективная")
                    click.echo(f"   📊 Сообщений: {msg_count}")

                    if complaints:
                        click.echo(f"   💰 Жалобы: {', '.join([f.fact_value for f in complaints])}")
                    if dreams:
                        click.echo(f"   ✨ Мечты: {', '.join([f.fact_value for f in dreams])}")

                    missing = []
                    if not complaints:
                        missing.append("жалобы на деньги")
                    if not dreams:
                        missing.append("дорогие мечты")
                    if msg_count < 30:
                        missing.append(f"больше общения (сейчас {msg_count})")

                    if missing:
                        click.echo(f"   📝 Нужно: {', '.join(missing)}")

            # Показываем низкие возможности если запрошено
            if low_opportunities and show_all:
                click.echo(f"\n💬 НАЧАЛЬНАЯ СТАДИЯ (продолжать общение):")
                for chat, complaints, dreams, work, msg_count in low_opportunities[:5]:
                    name = chat.first_name or "Без имени"
                    click.echo(f"   👤 {name} (ID: {chat.id}): {msg_count} сообщений - продолжать знакомство")

            if not opportunities_found:
                click.echo("📭 Пока нет явных возможностей для предложения работы")
                click.echo("\n💡 Советы:")
                click.echo("   • Продолжайте развивать диалоги")
                click.echo("   • Выявляйте жалобы на работу и деньги")
                click.echo("   • Интересуйтесь дорогими мечтами (машины, путешествия)")
                click.echo("   • Набирайте больше сообщений для доверия")
            else:
                click.echo(f"\n📊 Итого возможностей:")
                click.echo(f"   🔥 Высокие: {len(high_opportunities)}")
                click.echo(f"   ⚡ Средние: {len(medium_opportunities)}")
                if show_all:
                    click.echo(f"   💬 Начальные: {len(low_opportunities)}")

        except Exception as e:
            click.echo(f"❌ Ошибка анализа возможностей: {e}")

    @staticmethod
    @click.command()
    def dev():
        """⚡ Дев режим - быстрая статистика конверсии"""
        try:
            conversion_stats = db_manager.get_conversion_stats()

            if not conversion_stats:
                click.echo("📭 Нет данных о диалогах")
                return

            click.echo(f"\n⚡ ДЕВ РЕЖИМ - Статистика конверсии:")
            click.echo("=" * 60)

            total = conversion_stats['total_dialogues']
            click.echo(f"📊 Всего диалогов: {total}")

            if total > 0:
                click.echo(f"\n📈 Воронка конверсии:")
                click.echo(
                    f"   🔍 Фильтрация:  {conversion_stats.get('day1_filtering', 0)} ({conversion_stats.get('day1_filtering', 0) / total * 100:.1f}%)")
                click.echo(
                    f"   💕 Углубление:   {conversion_stats.get('day3_deepening', 0)} ({conversion_stats.get('day3_deepening', 0) / total * 100:.1f}%)")
                click.echo(
                    f"   💼 Предложение:  {conversion_stats.get('day5_offering', 0)} ({conversion_stats.get('day5_offering', 0) / total * 100:.1f}%)")

                click.echo(f"\n🎯 РЕЗУЛЬТАТЫ:")
                wants_call = conversion_stats.get('wants_call', 0)
                agreed = conversion_stats.get('agreed_to_help', 0)
                click.echo(f"   📞 Хотят созвониться: {wants_call}")
                click.echo(f"   ✅ Согласны помочь:   {agreed}")

                click.echo(f"\n💯 КОНВЕРСИЯ: {conversion_stats.get('conversion_rate', 0):.1f}%")

                if conversion_stats.get('conversion_rate', 0) > 0:
                    click.echo("🎉 Есть успешные конверсии!")
                else:
                    click.echo("❌ Пока нет успешных конверсий")
                    click.echo("💡 Продолжайте тестировать диалоги")

        except Exception as e:
            click.echo(f"❌ Ошибка дев статистики: {e}")

# Создаем экземпляр для экспорта команд
stats_commands = StatsCommands()