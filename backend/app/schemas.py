from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    source_url: str | None = None
    content: str = Field(min_length=20, max_length=100_000)


class DocumentRead(BaseModel):
    id: str
    title: str
    source_url: str | None
    redacted_items: int
    chunks: int
    created_at: datetime


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1_000)
    top_k: int = Field(default=4, ge=1, le=8)


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    excerpt: str
    score: float


class AskResponse(BaseModel):
    answer: str
    grounded: bool
    abstained: bool
    confidence: float
    citations: list[Citation]
    model: str


class EvaluationResult(BaseModel):
    cases: int
    retrieval_recall_at_k: float
    citation_coverage: float
    abstention_rate: float
    details: list[dict[str, Any]]
