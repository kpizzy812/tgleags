"""
Общий помощник для OpenAI API с retry логикой
"""
import asyncio
import json
from typing import Dict, Optional
from openai import OpenAI
from loguru import logger

from ..config.settings import settings


class OpenAIHelper:
    """Wrapper для OpenAI API с обработкой ошибок"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=60.0
        )

    async def get_json_response(self, prompt: str, max_tokens: int = 400,
                                temperature: float = 0.3) -> Optional[Dict]:
        """Получить JSON ответ с retry логикой"""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60
                )

                content = response.choices[0].message.content.strip()
                if not content:
                    raise ValueError("Пустой ответ от OpenAI")

                return json.loads(content)

            except json.JSONDecodeError as e:
                logger.warning(f"Ошибка JSON в попытке {attempt + 1}: {e}")
                if attempt == 2:
                    return None

            except Exception as e:
                logger.warning(f"Ошибка OpenAI в попытке {attempt + 1}: {e}")
                if attempt == 2:
                    return None

                # Ждем перед повтором
                await asyncio.sleep(2 ** attempt)

        return None

    async def get_text_response(self, prompt: str, max_tokens: int = 150,
                                temperature: float = 0.7) -> Optional[str]:
        """Получить текстовый ответ с retry логикой"""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60
                )

                return response.choices[0].message.content.strip()

            except Exception as e:
                logger.warning(f"Ошибка OpenAI в попытке {attempt + 1}: {e}")
                if attempt == 2:
                    return None

                await asyncio.sleep(2 ** attempt)

        return None


# Глобальный экземпляр
openai_helper = OpenAIHelper()