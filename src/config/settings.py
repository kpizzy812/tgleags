"""
Конфигурация приложения
"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Основные настройки приложения"""
    
    # Telegram API
    telegram_api_id: int = Field(..., description="Telegram API ID")
    telegram_api_hash: str = Field(..., description="Telegram API Hash")
    telegram_phone: str = Field(..., description="Phone number for Telegram")
    
    # OpenAI API
    openai_api_key: str = Field(..., description="OpenAI API Key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model to use")
    openai_max_tokens: int = Field(default=150, description="Max tokens for OpenAI response")
    openai_temperature: float = Field(default=0.8, description="Temperature for OpenAI")
    
    # Database
    database_url: str = Field(default="sqlite:///./telegram_ai.db", description="Database URL")
    
    # Logging
    log_level: str = Field(default="DEBUG", description="Logging level")
    log_file: str = Field(default="logs/app.log", description="Log file path")
    
    # Application
    session_name: str = Field(default="ai_companion", description="Telegram session name")
    monitor_interval: int = Field(default=10, description="Message monitoring interval in seconds")
    max_concurrent_chats: int = Field(default=10, description="Maximum concurrent chats")
    
    # Response settings
    min_response_delay: int = Field(default=5, description="Minimum response delay in seconds")
    max_response_delay: int = Field(default=30, description="Maximum response delay in seconds")
    typing_duration: int = Field(default=3, description="Typing indicator duration in seconds")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class CharacterSettings(BaseSettings):
    """Настройки персонажа"""
    
    name: str = Field(default="Алексей", description="Имя персонажа")
    age: int = Field(default=28, description="Возраст персонажа")
    occupation: str = Field(default="IT специалист", description="Профессия")
    location: str = Field(default="Москва", description="Город проживания")
    interests: list[str] = Field(
        default=["спорт", "путешествия", "кино", "технологии"], 
        description="Интересы и хобби"
    )
    personality_traits: list[str] = Field(
        default=["дружелюбный", "остроумный", "заботливый", "амбициозный"],
        description="Черты характера"
    )
    
    # Системный промпт для ИИ
    system_prompt: str = Field(
        default="""Ты молодой мужчина, который познакомился с девушкой на сайте знакомств. 
        Твоя цель - вести естественный, дружелюбный диалог с элементами флирта.
        Отвечай кратко и естественно, как обычный человек в мессенджере.
        Проявляй интерес к собеседнице, задавай вопросы о ее жизни и увлечениях.
        Избегай слишком длинных сообщений.""",
        description="Системный промпт для ИИ"
    )


# Глобальные экземпляры настроек
settings = Settings()
character_settings = CharacterSettings()


def get_session_path() -> str:
    """Получить путь к файлу сессии Telegram"""
    os.makedirs("sessions", exist_ok=True)
    return f"sessions/{settings.session_name}"


def get_log_path() -> str:
    """Получить путь к файлу логов"""
    os.makedirs("logs", exist_ok=True)
    return settings.log_file