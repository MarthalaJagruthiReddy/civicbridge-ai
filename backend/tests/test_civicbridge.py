from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.ai.retrieval import HashingEmbedder  # noqa: E402
from app.ai.service import AnswerService  # noqa: E402
from app.main import create_app  # noqa: E402


def make_client(tmp_path):
    service = AnswerService(embedder=HashingEmbedder())
    app = create_app(f"sqlite:///{tmp_path / 'civicbridge.db'}", service)
    return TestClient(app)


def test_ingestion_redacts_and_ask_returns_citation(tmp_path):
    client = make_client(tmp_path)
    ingest = client.post("/api/v1/documents", json={
        "title": "Downtown Shelter",
        "source_url": "https://example.org/shelter",
        "content": "The downtown shelter is open every day from 8 AM to 8 PM. Contact team@example.org for an intake appointment.",
    })
    assert ingest.status_code == 201
    assert ingest.json()["redacted_items"] == 1

    answer = client.post("/api/v1/ask", json={"question": "When is the downtown shelter open?"})
    body = answer.json()
    assert answer.status_code == 200
    assert body["grounded"] is True
    assert body["citations"][0]["document_title"] == "Downtown Shelter"
    assert "8 AM" in body["answer"]


def test_system_abstains_when_no_grounded_context_exists(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/v1/documents", json={"title": "Kitchen", "content": "The community kitchen serves vegetarian meals on Tuesday."})
    answer = client.post("/api/v1/ask", json={"question": "What is the lunar launch window?"})
    body = answer.json()
    assert body["abstained"] is True
    assert body["citations"] == []
