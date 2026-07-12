"""Loads and caches company knowledge from local text/markdown files.

The knowledge base is read once at server startup and kept in memory for
the lifetime of the process. It is never re-read from disk unless the
server restarts.
"""

from pathlib import Path

from app.config import KNOWLEDGE_DIR

_SUPPORTED_EXTENSIONS = {".md", ".txt"}

# Module-level cache. Populated once by load_knowledge_base().
_knowledge_cache: str | None = None


def load_knowledge_base() -> str:
    """Read every .md/.txt file in the knowledge directory and merge them.

    Results are cached in memory after the first call, so subsequent
    calls return the same string without touching the filesystem again.
    """
    global _knowledge_cache

    if _knowledge_cache is not None:
        return _knowledge_cache

    if not KNOWLEDGE_DIR.exists():
        _knowledge_cache = ""
        return _knowledge_cache

    sections: list[str] = []
    for file_path in sorted(Path(KNOWLEDGE_DIR).iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in _SUPPORTED_EXTENSIONS:
            content = file_path.read_text(encoding="utf-8").strip()
            if content:
                sections.append(f"# Source: {file_path.name}\n{content}")

    _knowledge_cache = "\n\n---\n\n".join(sections)
    return _knowledge_cache


def get_cached_knowledge() -> str:
    """Return the in-memory knowledge base, loading it if necessary."""
    return load_knowledge_base()
