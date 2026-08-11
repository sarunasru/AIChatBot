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
DATA_DIR = BASE_DIR / "data"


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
    model: str = os.getenv("MODEL", "google/gemini-3.1-flash-lite")
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

    # --- Contact form / email (SMTP) --------------------------------------
    # Where staff-contact messages are delivered, and the From address they
    # appear to come from. contact_from_email should be on a domain the SMTP
    # server is authorised to send for (e.g. the mailbox's own domain).
    contact_to_email: str = os.getenv("CONTACT_TO_EMAIL", "")
    contact_from_email: str = os.getenv("CONTACT_FROM_EMAIL", "")

    # Per-IP limit on POST /contact. Sending email is an abuse magnet, so this
    # is deliberately much stricter than the chat limit.
    contact_rate_limit: str = os.getenv("CONTACT_RATE_LIMIT", "5/hour")

    # SMTP relay used to send the contact emails.
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _get_int("SMTP_PORT", 587)
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes")

    # --- Chat logging (SQLite) --------------------------------------------
    # Each user->assistant exchange is stored in this SQLite file. Keep it on a
    # mounted volume (see docker-compose) so it survives container rebuilds.
    chat_log_db_path: Path = DATA_DIR / os.getenv("CHAT_LOG_DB", "chat_logs.db")
    # Logs older than this are pruned at startup. Set to 0 to keep forever.
    chat_log_retention_days: int = _get_int("CHAT_LOG_RETENTION_DAYS", 90)


settings = Settings()
