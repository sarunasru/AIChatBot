"""Thin wrapper around the embeddings API (OpenAI-compatible).

Used by tools/build_embeddings.py to vectorise the chunks offline, and by
app.retrieval to vectorise each incoming question. Multilingual model, so a
question in any language matches the Lithuanian chunks.
"""

import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger("faq_assistant")

_client: OpenAI | None = None


class EmbeddingError(Exception):
    """Raised when the embeddings API cannot be reached or is misconfigured."""


def _get_client() -> OpenAI:
    global _client
    if not settings.embedding_api_key:
        raise EmbeddingError("EMBEDDING_API_KEY nenustatytas .env faile.")
    if _client is None:
        _client = OpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            timeout=settings.request_timeout,
        )
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return an embedding vector for each input text (order preserved)."""
    client = _get_client()
    kwargs = {"model": settings.embedding_model, "input": texts}
    if settings.embedding_dimensions > 0:
        kwargs["dimensions"] = settings.embedding_dimensions
    try:
        resp = client.embeddings.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 - surface any API failure uniformly
        raise EmbeddingError(str(exc)) from exc
    return [item.embedding for item in resp.data]


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]
