"""Embed every chunk in site_chunks.jsonl and save the vectors to site_vectors.npy.

Run offline whenever the chunks change (after tools/clean_scrape.py):
    python tools/build_embeddings.py

Needs EMBEDDING_API_KEY in .env. The resulting .npy is aligned row-for-row with
site_chunks.jsonl and is committed so the server never re-embeds the whole corpus.
"""

import json
import time
from pathlib import Path

import numpy as np

from app.config import settings
from app.embeddings import EmbeddingError, embed_texts

BATCH = 64
# Free Jina tier caps ~100k tokens/min; stay well under it (chars/4 ~= tokens).
TOKENS_PER_MIN_BUDGET = 80_000


def _embed_with_retry(batch: list[str]) -> list[list[float]]:
    for attempt in range(5):
        try:
            return embed_texts(batch)
        except EmbeddingError as exc:
            if "429" in str(exc) or "rate" in str(exc).lower():
                wait = 20 * (attempt + 1)
                print(f"    rate limited; waiting {wait}s ...")
                time.sleep(wait)
                continue
            raise
    raise EmbeddingError("Gave up after repeated rate-limit errors.")


def main() -> None:
    chunks_path = settings.site_chunks_path
    out_path = settings.site_vectors_path

    texts = []
    for line in chunks_path.open(encoding="utf-8"):
        line = line.strip()
        if line:
            texts.append(json.loads(line)["text"])
    print(f"Embedding {len(texts)} chunks with {settings.embedding_model} ...")

    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i : i + BATCH]
        vectors.extend(_embed_with_retry(batch))
        print(f"  {min(i + BATCH, len(texts))}/{len(texts)}")
        # Pace to respect the tokens-per-minute budget.
        batch_tokens = sum(len(t) for t in batch) / 4
        time.sleep(min(60.0, batch_tokens / TOKENS_PER_MIN_BUDGET * 60))

    arr = np.asarray(vectors, dtype=np.float32)
    # Pre-normalise so runtime similarity is a plain dot product.
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    arr = arr / np.clip(norms, 1e-8, None)
    np.save(out_path, arr)
    print(f"Saved {arr.shape} -> {out_path}")


if __name__ == "__main__":
    main()
