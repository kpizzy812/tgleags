"""
Вспомогательные функции и утилиты
"""

from .helpers import (
    setup_logging, get_random_delay, get_smart_delay, clean_text, extract_keywords,
    is_question, simulate_typing, get_time_based_greeting, add_random_typo,
    format_chat_history_for_ai
)

__all__ = [
    'setup_logging', 'get_random_delay', 'get_smart_delay', 'clean_text', 'extract_keywords',
    'is_question', 'simulate_typing', 'get_time_based_greeting', 'add_random_typo',
    'format_chat_history_for_ai'
]
