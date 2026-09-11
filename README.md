# CivicBridge AI

CivicBridge AI turns messy community-resource updates into a safer, searchable knowledge base. It redacts obvious contact data before indexing, stores the document/chunk index in MongoDB, retrieves relevant passages, cites the source, and abstains when confidence is too low.

## AI design

- `HashingEmbedder` is an offline deterministic baseline so the project can run without a paid API.
- MongoDB stores source documents and chunk embeddings; Atlas Vector Search can replace the small offline cosine loop at deployment time.
- If `OPENAI_API_KEY` and the optional `openai` package are present, the same interface uses hosted embeddings and a grounded chat model.
- The answer prompt receives only retrieved context; citations are returned separately so the UI can expose provenance.
- The evaluation endpoint measures retrieval recall, citation coverage, and abstention rate over a small golden set.

This makes the AI claim testable: a recruiter can inspect the retrieval boundary, the fallback, the evaluator, the PII-redaction step, and the MongoDB persistence path. SQLite remains a local fallback for unit tests.

## Run

```bash
npm install
docker compose up --build
```

Open `http://localhost:8002/docs`. Run the frontend with:

```bash
npm run dev
```

## Interview discussion

1. Why is retrieval confidence not the same thing as answer correctness?
2. What would change when moving from JSON embeddings to Postgres + pgvector?
3. How would you evaluate hallucinations and stale resource availability?
4. What privacy threats remain after regex redaction, and how would you improve the detector?

## Honest evaluation plan

Expand `EVAL_CASES` with 50 reviewed questions, compare the offline baseline with the hosted model, and record recall@k, citation precision, grounded-answer rate, abstention rate, p95 latency, and cost per question. Only measured results belong in a resume bullet.
