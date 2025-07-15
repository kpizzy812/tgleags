"""
Вспомогательные функции и утилиты
"""

from .helpers import (
    setup_logging, get_random_delay, clean_text, extract_keywords,
    is_question, should_respond_to_message, simulate_typing,
    get_time_based_greeting, add_random_typo
)

__all__ = [
    "setup_logging", "get_random_delay", "clean_text", "extract_keywords",
    "is_question", "should_respond_to_message", "simulate_typing", 
    "get_time_based_greeting", "add_random_typo"
]
