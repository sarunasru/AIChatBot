"""Multilingual retrieval over the cleaned website chunks.

Primary: semantic search using precomputed embedding vectors (site_vectors.npy)
against the embedded question, so a question in any language matches the
Lithuanian chunks. Fallback: if the embeddings API is unavailable, a keyword
FTS5 search still returns something rather than nothing.

app.ai adds the top matches to the prompt on top of the always-on curated core.
"""

import json
import logging
import re
import sqlite3
import threading

import numpy as np

from app.config import settings
from app.embeddings import EmbeddingError, embed_texts

logger = logging.getLogger("faq_assistant")

_chunks: list[dict] = []
_vectors: np.ndarray | None = None
_fts: sqlite3.Connection | None = None
_lock = threading.Lock()

_STOPWORDS = {
    "ir", "ar", "kaip", "kur", "kada", "yra", "man", "su", "ne", "dėl", "apie",
    "the", "a", "an", "is", "are", "in", "to", "of", "do", "can", "i", "how",
    "what", "where", "when", "at",
}


def init_retrieval() -> None:
    """Load chunks + their vectors, and build the keyword fallback index."""
    global _chunks, _vectors, _fts

    path = settings.site_chunks_path
    if not path.exists():
        logger.warning("Retrieval disabled: chunk file not found at %s", path)
        return

    _chunks = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                _chunks.append(json.loads(line))

    # Vectors for semantic search (row-aligned with _chunks).
    if settings.site_vectors_path.exists():
        vecs = np.load(settings.site_vectors_path)
        if vecs.shape[0] == len(_chunks):
            _vectors = vecs
            logger.info("Retrieval: loaded %d embedding vectors.", vecs.shape[0])
        else:
            logger.error(
                "Vector count (%d) != chunk count (%d); rebuild site_vectors.npy. "
                "Falling back to keyword search.", vecs.shape[0], len(_chunks),
            )
    else:
        logger.warning("No site_vectors.npy; using keyword search only.")

    _fts = _build_fts(_chunks)
    logger.info("Retrieval index ready (%d chunks).", len(_chunks))


def _build_fts(chunks: list[dict]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute(
        "CREATE VIRTUAL TABLE chunks USING fts5(text, idx UNINDEXED, "
        "tokenize = 'unicode61 remove_diacritics 2')"
    )
    conn.executemany(
        "INSERT INTO chunks (text, idx) VALUES (?, ?)",
        [(c["text"], i) for i, c in enumerate(chunks)],
    )
    conn.commit()
    return conn


def search(question: str, context: str | None = None, limit: int | None = None) -> list[dict]:
    """Return up to `limit` chunks most relevant to `question`.

    If `context` (recent conversation) is given, a chunk is scored by the BEST
    match against either the question or the context. This keeps follow-up
    questions ("what are his contacts?") working via the context, while a new
    topic ("is there a kids' room?") still matches on the question alone - so an
    earlier topic can never drag the search off a fresh, self-contained question.

    Tries semantic (embedding) search first, then keyword search. Never raises -
    returns [] so the chat still answers from the curated core.
    """
    if not _chunks:
        return []
    k = limit or settings.retrieval_top_k

    if _vectors is not None:
        try:
            queries = [question] + ([context] if context else [])
            qmat = np.asarray(embed_texts(queries), dtype=np.float32)
            qmat /= np.clip(np.linalg.norm(qmat, axis=1, keepdims=True), 1e-8, None)
            # Best (max) similarity to any query, per chunk.
            scores = (_vectors @ qmat.T).max(axis=1)
            top = np.argsort(-scores)[:k]
            return [_chunks[i] for i in top]
        except EmbeddingError as exc:
            logger.error("Embedding search failed, falling back to keyword: %s", exc)

    return _keyword_search(question, k)


def _keyword_search(question: str, k: int) -> list[dict]:
    if _fts is None:
        return []
    match = _build_match_query(question)
    if not match:
        return []
    try:
        with _lock:
            cur = _fts.execute(
                "SELECT idx FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ?",
                (match, k),
            )
            return [_chunks[row[0]] for row in cur.fetchall()]
    except sqlite3.Error as exc:
        logger.error("Keyword fallback failed: %s", exc)
        return []


def _build_match_query(question: str) -> str:
    words = re.findall(r"\w+", question.lower())
    terms = []
    for w in words:
        if len(w) < 3 or w in _STOPWORDS:
            continue
        terms.append(f'"{w}"*')
    return " OR ".join(terms[:10])
