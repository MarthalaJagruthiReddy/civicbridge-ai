from prometheus_client import Counter


documents_ingested = Counter("civicbridge_documents_ingested_total", "Documents accepted for indexing")
questions_answered = Counter("civicbridge_questions_answered_total", "Questions processed")
abstentions = Counter("civicbridge_abstentions_total", "Questions where the system declined to guess")
