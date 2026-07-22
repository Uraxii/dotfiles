"""kb_embeddings.py — shared OpenRouter embedding helpers for the KB.

Used by build-kb-index.py (embed each docs/kb/*.md entry at build time) and
kb-search.py (embed the query at search time). Both must use the same
model, hence the shared constant here rather than one copy per script.

No key handling here: callers read OPENROUTER_API_KEY from the environment
and pass it in. This module never reads env vars or persists the key.
"""
from __future__ import annotations

import json
import urllib.request
from collections.abc import Sequence

import numpy as np

__all__ = [
    "EMBEDDING_MODEL",
    "EMBEDDING_SCHEMA",
    "EMBEDDING_ERRORS",
    "fetch_embedding",
    "vector_to_blob",
    "blob_to_vector",
]

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_TIMEOUT_SEC = 30.0

# One vector per KB entry, keyed by path. model + dim ride along so a future
# model swap is detectable (query and document vectors must share a model).
EMBEDDING_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS kb_embedding ("
    "path TEXT PRIMARY KEY, model TEXT, dim INTEGER, vector BLOB);"
)

# ponytail: one tuple of stdlib/OSError-family exceptions covers "network
# unreachable" (OSError, which urllib.error.URLError subclasses) and
# "response wasn't the shape we expected" (ValueError for bad JSON,
# KeyError/IndexError for a missing data[0].embedding). Callers catch this
# one tuple instead of enumerating urllib internals themselves.
EMBEDDING_ERRORS = (OSError, ValueError, KeyError, IndexError)


def fetch_embedding(
    text: str, api_key: str, timeout: float = EMBEDDING_TIMEOUT_SEC,
) -> list[float]:
    """Call OpenRouter's embeddings endpoint, return one embedding vector.

    Raises one of EMBEDDING_ERRORS on network failure or an unexpected
    response shape; callers decide how to degrade (skip vectors, fall back
    to keyword search, etc).
    """
    payload = json.dumps({"model": EMBEDDING_MODEL, "input": text}).encode("utf-8")
    request = urllib.request.Request(
        OPENROUTER_EMBEDDINGS_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["data"][0]["embedding"]


def vector_to_blob(vector: Sequence[float]) -> bytes:
    """Pack an embedding vector as float32 bytes for the vector BLOB column."""
    return np.asarray(vector, dtype=np.float32).tobytes()


def blob_to_vector(blob: bytes) -> np.ndarray:
    """Unpack a vector BLOB column back into a float32 numpy array."""
    return np.frombuffer(blob, dtype=np.float32)
