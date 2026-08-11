"""Stores chat exchanges in a local SQLite file for later review/analytics.

One row per user->assistant exchange. No separate database server: SQLite is a
single file (see DB_PATH) kept on a mounted volume so it survives rebuilds.

Kept intentionally small - the rest of the app only calls `init_db()` once at
startup and `log_exchange()` after each answer.
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from app.config import settings

logger = logging.getLogger("faq_assistant")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.chat_log_db_path, timeout=10)
    # WAL lets reads and the occasional write coexist without locking errors.
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create the logs table if needed and prune anything past the retention window."""
    settings.chat_log_db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                created_at TEXT NOT NULL,
                user_message TEXT NOT NULL,
                assistant_reply TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_logs_created_at ON chat_logs(created_at)")
    _prune_old_logs()


def _prune_old_logs() -> None:
    """Delete logs older than the configured retention window (privacy hygiene)."""
    if settings.chat_log_retention_days <= 0:
        return
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=settings.chat_log_retention_days)
    ).isoformat()
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM chat_logs WHERE created_at < ?", (cutoff,))
    except sqlite3.Error as exc:
        logger.error("Failed to prune old chat logs: %s", exc)


def log_exchange(session_id: str, user_message: str, assistant_reply: str) -> None:
    """Persist a single exchange. Never raises - logging must not break /chat."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO chat_logs (session_id, created_at, user_message, assistant_reply) "
                "VALUES (?, ?, ?, ?)",
                (
                    session_id or None,
                    datetime.now(timezone.utc).isoformat(),
                    user_message,
                    assistant_reply,
                ),
            )
    except sqlite3.Error as exc:
        logger.error("Failed to write chat log: %s", exc)
