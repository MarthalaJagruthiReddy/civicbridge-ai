from __future__ import annotations

from dataclasses import dataclass

from ..models import Chunk, Document


@dataclass
class RetrievedChunkLike:
    chunk: Chunk
    document: Document
    score: float
