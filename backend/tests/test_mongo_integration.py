from datetime import datetime, timezone
import os

import pytest

from app.ai.mongo_store import MongoKnowledgeStore
from app.models import Chunk, Document


@pytest.mark.skipif(os.getenv("MONGO_INTEGRATION") != "1", reason="requires the MongoDB integration environment")
def test_mongodb_store_round_trip():
    store = MongoKnowledgeStore(os.environ["MONGO_URI"], os.getenv("MONGO_DATABASE", "civicbridge_test"))
    document_id = "integration-document"
    document = Document(
        id=document_id,
        title="Integration shelter",
        source_url="https://example.org/integration",
        content="The shelter is open today.",
        redacted_items=0,
        created_at=datetime.now(timezone.utc),
    )
    chunk = Chunk(
        id="integration-chunk",
        document_id=document_id,
        ordinal=0,
        text="The shelter is open today.",
        token_count=5,
        embedding=[1.0, 0.0],
    )

    try:
        store.collection.delete_many({"_id": document_id})
        store.save_document(document, [chunk])
        matches = store.retrieve([1.0, 0.0], top_k=1, query_terms={"shelter"})
        assert len(matches) == 1
        assert matches[0].document.title == "Integration shelter"
        assert matches[0].chunk.text == "The shelter is open today."
    finally:
        store.collection.delete_many({"_id": document_id})
        store.client.close()
