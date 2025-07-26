"""
Вспомогательные функции и утилиты
"""

from .helpers import (
    setup_logging, get_random_delay, get_smart_delay, clean_text, extract_keywords,
    is_question, get_time_based_greeting, add_random_typo,
    format_chat_history_for_ai
)
from .openai_helper import openai_helper

__all__ = [
    'setup_logging', 'get_random_delay', 'get_smart_delay', 'clean_text', 'extract_keywords',
    'is_question', 'get_time_based_greeting', 'add_random_typo',
    'format_chat_history_for_ai', "openai_helper"
]