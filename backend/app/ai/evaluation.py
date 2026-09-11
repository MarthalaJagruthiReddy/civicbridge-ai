from __future__ import annotations

from sqlalchemy.orm import Session

from .service import AnswerService


EVAL_CASES = [
    {"question": "When is the downtown shelter open?", "terms": ["open", "shelter"], "source": "Downtown Shelter"},
    {"question": "Which location offers vegetarian meals?", "terms": ["vegetarian", "meals"], "source": "Community Kitchen"},
    {"question": "Can I get legal help on Sunday?", "terms": ["legal", "sunday"], "source": "Legal Aid"},
]


def run_evaluation(session: Session, service: AnswerService) -> dict:
    details = []
    recalled = 0
    cited = 0
    abstained = 0
    for case in EVAL_CASES:
        result = service.ask(session, case["question"], top_k=4)
        text = result["answer"].lower()
        citation_titles = {citation["document_title"] for citation in result["citations"]}
        has_terms = all(term in text or any(term in citation["excerpt"].lower() for citation in result["citations"]) for term in case["terms"])
        has_source = case["source"] in citation_titles
        recalled += int(has_terms)
        cited += int(has_source)
        abstained += int(result["abstained"])
        details.append({"question": case["question"], "recalled": has_terms, "source_cited": has_source, "abstained": result["abstained"]})
    total = len(EVAL_CASES)
    return {"cases": total, "retrieval_recall_at_k": round(recalled / total, 3), "citation_coverage": round(cited / total, 3), "abstention_rate": round(abstained / total, 3), "details": details}
