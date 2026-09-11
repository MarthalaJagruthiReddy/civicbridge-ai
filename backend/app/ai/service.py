from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..metrics import abstentions, documents_ingested, questions_answered
from ..models import Chunk, Document
from .redaction import redact_pii
from .retrieval import Embedder, chunk_text, choose_embedder, cosine, meaningful_tokens


@dataclass
class RetrievedChunk:
    chunk: Chunk
    document: Document
    score: float


class OpenAIAnswerGenerator:
    name = "openai-grounded"

    def __init__(self):
        from openai import OpenAI  # type: ignore[import-not-found]

        self.client = OpenAI()
        self.model = os.getenv("CHAT_MODEL", "gpt-4o-mini")

    def generate(self, question: str, context: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Answer only from the provided sources. If the sources do not support the answer, say you do not have enough information."},
                {"role": "user", "content": f"Question: {question}\n\nSources:\n{context}"},
            ],
        )
        return response.choices[0].message.content or "I could not produce a grounded answer."


class AnswerService:
    """Index, retrieve, abstain, cite, and optionally call a grounded LLM."""

    def __init__(self, embedder: Embedder | None = None, mongo_store=None):
        self.embedder = embedder or choose_embedder()
        self.mongo_store = mongo_store
        self.generator = None
        if os.getenv("OPENAI_API_KEY"):
            try:
                self.generator = OpenAIAnswerGenerator()
            except ImportError:
                self.generator = None

    def ingest(self, session: Session, title: str, source_url: str | None, content: str) -> Document:
        safe_content, redacted = redact_pii(content)
        document = Document(id=str(uuid.uuid4()), title=title, source_url=source_url, content=safe_content, redacted_items=redacted)
        session.add(document)
        indexed_chunks: list[Chunk] = []
        for ordinal, text in enumerate(chunk_text(safe_content)):
            chunk = Chunk(id=str(uuid.uuid4()), document_id=document.id, ordinal=ordinal, text=text, token_count=len(text.split()), embedding=self.embedder.embed(text))
            session.add(chunk)
            indexed_chunks.append(chunk)
        session.commit()
        session.refresh(document)
        if self.mongo_store:
            try:
                self.mongo_store.save_document(document, indexed_chunks)
            except Exception:
                # SQL metadata remains available while MongoDB recovers.
                pass
        documents_ingested.inc()
        return document

    def retrieve(self, session: Session, question: str, top_k: int = 4) -> list[RetrievedChunk]:
        query_vector = self.embedder.embed(question)
        query_terms = meaningful_tokens(question)
        if self.mongo_store:
            try:
                return self.mongo_store.retrieve(query_vector, top_k, query_terms)
            except Exception:
                # Keep the API useful in local/offline mode and during index recovery.
                pass
        rows = session.execute(select(Chunk, Document).join(Document, Document.id == Chunk.document_id)).all()
        ranked = []
        for chunk, document in rows:
            score = cosine(query_vector, chunk.embedding)
            # The offline hashing baseline is intentionally conservative: it
            # must share a meaningful term before it is allowed to ground an answer.
            if self.embedder.name == "hashing-baseline" and query_terms.isdisjoint(meaningful_tokens(chunk.text)):
                score = 0.0
            ranked.append(RetrievedChunk(chunk, document, score))
        return sorted(ranked, key=lambda item: item.score, reverse=True)[:top_k]

    def ask(self, session: Session, question: str, top_k: int = 4) -> dict:
        questions_answered.inc()
        retrieved = self.retrieve(session, question, top_k)
        confident = [item for item in retrieved if item.score >= 0.18]
        if not confident:
            abstentions.inc()
            return {"answer": "I do not have enough grounded information to answer that yet.", "grounded": False, "abstained": True, "confidence": 0.0, "citations": [], "model": self.embedder.name}

        citations = [
            {"chunk_id": item.chunk.id, "document_id": item.document.id, "document_title": item.document.title, "excerpt": item.chunk.text[:240], "score": round(item.score, 4)}
            for item in confident
        ]
        context = "\n\n".join(f"[{index + 1}] {item.chunk.text}" for index, item in enumerate(confident))
        if self.generator:
            answer = self.generator.generate(question, context)
            model = self.generator.name
        else:
            answer = self._extractive_answer(question, [item.chunk.text for item in confident])
            model = "extractive-offline-baseline"
        return {"answer": answer, "grounded": True, "abstained": False, "confidence": round(confident[0].score, 4), "citations": citations, "model": model}

    @staticmethod
    def _extractive_answer(question: str, contexts: list[str]) -> str:
        terms = {term for term in re.findall(r"[a-z0-9]+", question.lower()) if len(term) > 2}
        sentences = [sentence.strip() for context in contexts for sentence in re.split(r"(?<=[.!?])\s+", context) if sentence.strip()]
        scored = sorted(sentences, key=lambda sentence: len(terms.intersection(sentence.lower().split())), reverse=True)
        best = scored[:2]
        return " ".join(best) if best else "The indexed sources contain a matching passage, but no concise extractive answer was found."
