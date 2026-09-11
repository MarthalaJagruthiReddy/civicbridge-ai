from __future__ import annotations

import math
import os
import re
import hashlib
from collections.abc import Iterable
from typing import Protocol


class Embedder(Protocol):
    name: str

    def embed(self, text: str) -> list[float]: ...


TOKEN = re.compile(r"[a-z0-9']+")
STOPWORDS = {"the", "a", "an", "is", "are", "when", "what", "which", "where", "can", "i", "get", "on", "to", "for", "of", "and", "or", "in", "do"}


class HashingEmbedder:
    """Deterministic offline baseline; swap for a hosted/local embedding model in production."""

    name = "hashing-baseline"

    def __init__(self, dimensions: int = 64):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class OpenAIEmbedder:
    name = "openai-embedding"

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        from openai import OpenAI  # type: ignore[import-not-found]

        self.client = OpenAI()

    def embed(self, text: str) -> list[float]:
        result = self.client.embeddings.create(model=self.model, input=text)
        return list(result.data[0].embedding)


def choose_embedder() -> Embedder:
    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAIEmbedder(os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
        except ImportError:
            pass
    return HashingEmbedder()


def chunk_text(text: str, words_per_chunk: int = 110, overlap: int = 20) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + words_per_chunk)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks


def cosine(left: Iterable[float], right: Iterable[float]) -> float:
    a, b = list(left), list(right)
    denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if not denominator:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=False)) / denominator


def meaningful_tokens(text: str) -> set[str]:
    return {token for token in TOKEN.findall(text.lower()) if token not in STOPWORDS and len(token) > 2}
