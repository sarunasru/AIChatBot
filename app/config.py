"""Application configuration loaded from environment variables (.env)."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file located at the project root, if present.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Settings:
    """Strongly typed application settings."""

    api_key: str = os.getenv("LLM_API_KEY", "")
    base_url: str | None = os.getenv("LLM_BASE_URL") or None
    model: str = os.getenv("MODEL", "gpt-5.5")
    temperature: float = _get_float("TEMPERATURE", 0.2)
    max_tokens: int = _get_int("MAX_TOKENS", 1000)
    request_timeout: float = _get_float("REQUEST_TIMEOUT", 30.0)

    # Space-separated list of origins (CSP source expressions, e.g. "https://*.vu.lt
    # https://vu.lt") allowed to embed /widget in an <iframe>. Defaults to "'self'"
    # (no external embedding) so widget access must be explicitly opted into.
    widget_frame_ancestors: str = os.getenv("WIDGET_FRAME_ANCESTORS", "'self'")

    # Per-IP limit on POST /chat, in slowapi's "N/period" syntax (e.g. "10/minute").
    # Protects against a single client running up the LLM bill via scripted requests.
    chat_rate_limit: str = os.getenv("CHAT_RATE_LIMIT", "10/minute")


settings = Settings()
