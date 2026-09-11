from __future__ import annotations

import uuid
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .ai.evaluation import run_evaluation
from .ai.mongo_store import MongoKnowledgeStore
from .ai.service import AnswerService
from .db import Base, build_engine, build_session_factory, session_dependency
from .models import Chunk, Document
from .schemas import AskRequest, AskResponse, DocumentCreate, DocumentRead, EvaluationResult


def create_app(database_url: str | None = None, answer_service: AnswerService | None = None) -> FastAPI:
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    mongo_store = None
    if answer_service is None and os.getenv("MONGO_URI"):
        try:
            mongo_store = MongoKnowledgeStore(os.environ["MONGO_URI"], os.getenv("MONGO_DATABASE", "civicbridge"))
        except Exception:
            mongo_store = None
    service = answer_service or AnswerService(mongo_store=mongo_store)
    app = FastAPI(title="CivicBridge AI API", version="0.1.0", description="Grounded community-resource search with citations and abstention.")
    app.state.engine = engine
    app.state.session_factory = factory
    app.state.answer_service = service

    def get_session():
        yield from session_dependency(factory)

    @app.get("/healthz")
    def healthz(session: Session = Depends(get_session)):
        session.execute(text("SELECT 1"))
        storage = "sql-fallback"
        if service.mongo_store:
            storage = "mongodb" if service.mongo_store.healthy() else "mongodb-recovering"
        return {"status": "ok", "service": "civicbridge-ai", "model": service.embedder.name, "storage": storage}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/api/v1/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
    def ingest(command: DocumentCreate, session: Session = Depends(get_session)):
        document = service.ingest(session, command.title, command.source_url, command.content)
        chunks = session.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == document.id)) or 0
        return DocumentRead(id=document.id, title=document.title, source_url=document.source_url, redacted_items=document.redacted_items, chunks=chunks, created_at=document.created_at)

    @app.get("/api/v1/documents", response_model=list[DocumentRead])
    def list_documents(session: Session = Depends(get_session)):
        documents = list(session.scalars(select(Document).order_by(Document.created_at.desc())))
        return [DocumentRead(id=d.id, title=d.title, source_url=d.source_url, redacted_items=d.redacted_items, chunks=session.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == d.id)) or 0, created_at=d.created_at) for d in documents]

    @app.post("/api/v1/ask", response_model=AskResponse)
    def ask(command: AskRequest, session: Session = Depends(get_session)):
        return service.ask(session, command.question, command.top_k)

    @app.post("/api/v1/evals/run", response_model=EvaluationResult)
    def evaluate(session: Session = Depends(get_session)):
        return run_evaluation(session, service)

    return app


app = create_app()
