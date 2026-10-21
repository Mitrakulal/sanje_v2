"""All environment access for sanje-simple.

LangSmith reads its own environment variables directly, so loading `.env` here
is enough to turn tracing on. Nothing else in the project reads `os.environ`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=True)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    model_name: str = os.getenv("MODEL_NAME", "openai/gpt-oss-120b")
    cloud_endpoint: str = os.getenv("CLOUD_ENDPOINT", "https://api.groq.com/openai/v1")
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    max_tokens: int = int(os.getenv("MODEL_MAX_TOKENS", "1200"))

    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")

    tz_name: str = os.getenv("TZ", "Asia/Kolkata")
    langsmith_tracing: bool = _truthy(os.getenv("LANGSMITH_TRACING"))

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)

    @property
    def masked_model_key(self) -> str:
        if not self.api_key:
            return "(missing)"
        return f"{self.api_key[:7]}...{self.api_key[-4:]}"

    @property
    def masked_tavily_key(self) -> str:
        if not self.tavily_api_key:
            return "(missing)"
        return f"{self.tavily_api_key[:7]}...{self.tavily_api_key[-4:]}"

    def missing(self) -> list[str]:
        missing = []
        if not self.bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.api_key:
            missing.append("OPENAI_API_KEY")
        if not self.tavily_api_key:
            missing.append("TAVILY_API_KEY")
        return missing


SETTINGS = Settings()


def now() -> datetime:
    """Timezone-aware current time. Use this instead of datetime.now()."""
    return datetime.now(SETTINGS.tz)
