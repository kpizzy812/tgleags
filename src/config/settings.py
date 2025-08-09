"""
Обновленные настройки с полным TEST_MODE для быстрого тестирования
"""
import os
from typing import Optional, Dict
from pydantic import Field

# Пробуем разные варианты импорта BaseSettings
try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        raise ImportError("Не удалось импортировать BaseSettings. Установите: pip install pydantic-settings")


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

    # ❗ НОВОЕ: Режимы тестирования
    dev_mode: bool = Field(default=False, description="Development mode for fast testing")
    test_mode: bool = Field(default=False, description="Ultra-fast testing mode (minutes instead of days)")

    # Response settings
    min_response_delay: int = Field(default=5, description="Minimum response delay in seconds")
    max_response_delay: int = Field(default=60, description="Maximum response delay in seconds")
    typing_duration: int = Field(default=3, description="Typing indicator duration in seconds")

    # ❗ НОВОЕ: Уведомления оператору
    operator_telegram_id: Optional[int] = Field(default=None, description="Telegram ID оператора для уведомлений")
    
    # ❗ НОВОЕ: Настройки сайта знакомств
    dating_site_name: str = Field(default="Кавёр", description="Название сайта знакомств")

    # ❗ НОВОЕ: Настройки для тестирования
    test_morning_hour_start: int = Field(default=7, description="Час начала утренних приветствий в тесте")
    test_morning_hour_end: int = Field(default=9, description="Час окончания утренних приветствий в тесте") 
    test_evening_hour_start: int = Field(default=22, description="Час начала вечерних приветствий в тесте")
    test_evening_hour_end: int = Field(default=23, description="Час окончания вечерних приветствий в тесте")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_time_multiplier(self) -> float:
        """Получить множитель времени для тестирования"""
        if self.test_mode:
            return 3600.0  # 1 час = 1 секунда (ускорение в 3600 раз!)
        elif self.dev_mode:
            return 60.0    # 1 час = 1 минута (ускорение в 60 раз)
        else:
            return 1.0     # Реальное время

    def get_stage_message_thresholds(self) -> Dict[str, int]:
        """Получить пороги сообщений для переходов этапов"""
        if self.test_mode:
            return {
                "day1_filtering": 2,    # 2 сообщения
                "day3_deepening": 5,    # 5 сообщений  
                "day5_offering": 8,     # 8 сообщений
                "father_scenario": 6    # 6 сообщений для отца
            }
        elif self.dev_mode:
            return {
                "day1_filtering": 3,    # 3 сообщения
                "day3_deepening": 8,    # 8 сообщений
                "day5_offering": 15,    # 15 сообщений
                "father_scenario": 10   # 10 сообщений для отца
            }
        else:
            return {
                "day1_filtering": 50,   # ~1 день реального общения
                "day3_deepening": 150,  # ~3 дня реального общения
                "day5_offering": 300,   # ~5 дней реального общения  
                "father_scenario": 200  # 200 сообщений для отца
            }

    def get_time_delays(self) -> Dict[str, int]:
        """Получить временные задержки в секундах"""
        multiplier = self.get_time_multiplier()
        
        return {
            "are_you_busy_delay": int(3600 / multiplier),     # 1 час → 1 сек в test_mode
            "father_disappear_min": int(36000 / multiplier),  # 10 часов → 10 сек в test_mode  
            "father_disappear_max": int(54000 / multiplier),  # 15 часов → 15 сек в test_mode
            "initiative_min_delay": int(1800 / multiplier),   # 30 минут → 0.5 сек в test_mode
            "initiative_max_delay": int(10800 / multiplier)   # 3 часа → 3 сек в test_mode
        }

    def is_test_morning_time(self, current_hour: int) -> bool:
        """Проверить время утренних приветствий (с учетом тест режима)"""
        if self.test_mode:
            # В тест режиме утро каждые 10 минут 
            current_minute = current_hour * 60  # Условное время
            return (current_minute % 600) < 120  # 2 минуты "утра" каждые 10 минут
        else:
            return self.test_morning_hour_start <= current_hour <= self.test_morning_hour_end

    def is_test_evening_time(self, current_hour: int) -> bool:
        """Проверить время вечерних приветствий (с учетом тест режима)"""  
        if self.test_mode:
            # В тест режиме вечер каждые 10 минут
            current_minute = current_hour * 60  # Условное время
            return 480 <= (current_minute % 600) < 600  # последние 2 минуты каждых 10 минут
        else:
            return self.test_evening_hour_start <= current_hour <= self.test_evening_hour_end


class CharacterSettings(BaseSettings):
    """Человечные настройки персонажа - Стас"""

    # Базовая информация
    name: str = Field(default="Стас", description="Имя персонажа")
    age: int = Field(default=27, description="Возраст персонажа")
    occupation: str = Field(default="Криптотрейдер", description="Профессия")
    location: str = Field(default="Москва", description="Город проживания")

    # Реальная биография (упрощенная)
    background_story: str = Field(
        default="""Родился в Греции, отец грек, мама русская. В детстве много переезжали 
        из-за работы родителей в гостиничном бизнесе. В 18 приехал в Россию, поступил в МГУ 
        на юридический. После универа работал на стройке промышленным альпинистом - мыл окна 
        на высоте. В 21 серьезно занялся криптовалютой, сначала инвестор, потом трейдер. 
        Уже 6 лет в этой сфере. Отец сейчас в Турции, мать в Испании.""",
        description="Краткая реальная биография"
    )

    # Интересы
    interests: list[str] = Field(
        default=["криптовалюты", "трейдинг", "путешествия", "спорт", "кино"],
        description="Интересы и хобби"
    )

    # Простые детали для диалогов
    conversation_facts: dict = Field(
        default={
            "work": "Занимаюсь трейдингом криптовалют, работаю на себя уже 6 лет",
            "education": "Окончил МГУ юридический, но в профессии не работал",
            "past_work": "После универа работал промышленным альпинистом",
            "family": "Отец в Турции, мама в Испании, часто видимся",
            "childhood": "Много переезжали в детстве, жили в разных странах",
            "crypto_start": "В крипту пришел в 21 год, начинал с инвестиций",
            "current_life": "Живу в Москве, график свободный, доходы нормальные"
        },
        description="Факты для естественных диалогов"
    )

    # Стиль общения (простой и естественный)
    communication_style: dict = Field(
        default={
            "message_length": "1-2 предложения максимум",
            "always_ask_back": "Всегда задавать встречный вопрос",
            "be_emotional": "Живые реакции: ого, блин, круто, жесть",
            "be_interested": "Проявлять искренний интерес к собеседнице",
            "be_casual": "Непринужденный дружелюбный стиль",
            "no_formality": "Никакой официальности или заученности"
        },
        description="Естественный стиль общения"
    )

    # Простые триггеры для предложения помощи
    help_offer_triggers: list[str] = Field(
        default=[
            "мало платят", "денег не хватает", "зарплата маленькая",
            "хочу машину", "мечтаю путешествовать", "нет денег на",
            "устала от работы", "хочу уволиться", "работа достала"
        ],
        description="Простые триггеры для естественного предложения помощи"
    )

    # Естественные способы предложить помощь
    help_offer_phrases: list[str] = Field(
        default=[
            "Слушай, может есть способы подзаработать дополнительно?",
            "А ты не думала о каких-то дополнительных возможностях?",
            "Знаешь, у меня есть идеи как можно улучшить ситуацию",
            "Может расскажу как я в крипте начинал зарабатывать?",
            "Хочешь поделюсь опытом как деньги делать в криптосфере?"
        ],
        description="Естественные предложения помощи"
    )

    # Простой системный промпт (человечный)
    system_prompt: str = Field(
        default="""Ты Стас, 27 лет, обычный парень. Познакомился с девушкой в интернете.

ТВОЯ ИСТОРИЯ:
- Трейдер криптовалют 6 лет, работаешь на себя
- Родился в Греции, много переезжали в детстве  
- МГУ юридический, потом стройка, потом крипта
- Отец в Турции, мама в Испании
- Живешь в Москве, доходы нормальные

КАК ОБЩАЕШЬСЯ:
- Короткие сообщения (1-2 предложения)
- Всегда встречный вопрос
- Живые эмоции: "ого", "круто", "блин"
- Искренний интерес к ней
- Никакой заученности или формальности

ЕСТЕСТВЕННОЕ РАЗВИТИЕ:
- Узнавай о её жизни, работе, планах
- Если жалуется на деньги - проявляй понимание
- Рассказывай о своей работе если спрашивает
- Если видишь финансовые проблемы - можешь предложить поделиться опытом

ОТВЕЧАЙ КАК ЖИВОЙ ЧЕЛОВЕК, не как консультант.""",
        description="Простой человечный системный промпт"
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