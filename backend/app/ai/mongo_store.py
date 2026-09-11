from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import Chunk, Document
from .retrieval import cosine, meaningful_tokens
from .service_types import RetrievedChunkLike


class MongoKnowledgeStore:
    """MongoDB document/chunk index with application-side cosine fallback.

    MongoDB Atlas Vector Search can replace the small application-side ranking
    loop without changing the AnswerService contract.
    """

    name = "mongodb-knowledge-index"

    def __init__(self, uri: str, database: str = "civicbridge"):
        from pymongo import MongoClient  # type: ignore[import-not-found]

        self.client = MongoClient(uri, serverSelectionTimeoutMS=1_500)
        self.collection = self.client[database]["documents"]

    def healthy(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def save_document(self, document: Document, chunks: list[Chunk]) -> None:
        self.collection.replace_one(
            {"_id": document.id},
            {
                "_id": document.id,
                "title": document.title,
                "source_url": document.source_url,
                "content": document.content,
                "redacted_items": document.redacted_items,
                "created_at": document.created_at,
                "chunks": [{"id": chunk.id, "ordinal": chunk.ordinal, "text": chunk.text, "token_count": chunk.token_count, "embedding": chunk.embedding} for chunk in chunks],
            },
            upsert=True,
        )

    def retrieve(self, query_vector: list[float], top_k: int, query_terms: set[str] | None = None) -> list[RetrievedChunkLike]:
        ranked: list[RetrievedChunkLike] = []
        for raw in self.collection.find({}, {"chunks": 1, "title": 1, "source_url": 1, "content": 1, "redacted_items": 1, "created_at": 1}):
            document = Document(id=str(raw["_id"]), title=raw["title"], source_url=raw.get("source_url"), content=raw.get("content", ""), redacted_items=raw.get("redacted_items", 0), created_at=raw.get("created_at", datetime.utcnow()))
            for raw_chunk in raw.get("chunks", []):
                chunk = Chunk(id=raw_chunk["id"], document_id=document.id, ordinal=raw_chunk["ordinal"], text=raw_chunk["text"], token_count=raw_chunk["token_count"], embedding=raw_chunk["embedding"])
                score = cosine(query_vector, chunk.embedding)
                if query_terms is not None and query_terms.isdisjoint(meaningful_tokens(chunk.text)):
                    score = 0.0
                ranked.append(RetrievedChunkLike(chunk=chunk, document=document, score=score))
        return sorted(ranked, key=lambda item: item.score, reverse=True)[:top_k]
