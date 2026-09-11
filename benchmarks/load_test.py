from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
REQUESTS = int(os.getenv("REQUESTS", "300"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "20"))


def request_json(method: str, path: str, payload: dict | None = None) -> tuple[int, float]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"content-type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            return response.status, (time.perf_counter() - started) * 1000
    except Exception:
        return 0, (time.perf_counter() - started) * 1000


def percentile(values: list[float], value: int) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, (value * len(ordered) + 99) // 100 - 1))
    return round(ordered[index], 2)


def main() -> None:
    status, _ = request_json(
        "POST",
        "/api/v1/documents",
        {
            "title": "Benchmark shelter",
            "source_url": "https://example.org/benchmark",
            "content": "The downtown shelter is open today from 8 AM to 8 PM and provides meals.",
        },
    )
    if status != 201:
        raise SystemExit(f"seed document failed with HTTP {status}")

    def ask(_: int) -> tuple[int, float]:
        return request_json("POST", "/api/v1/ask", {"question": "When is the downtown shelter open?", "top_k": 4})

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        samples = list(executor.map(ask, range(REQUESTS)))
    elapsed = time.perf_counter() - started
    successful = [sample for sample in samples if sample[0] == 200]
    latencies = [sample[1] for sample in successful]
    result = {
        "benchmark": "CivicBridge grounded Q&A",
        "requests": REQUESTS,
        "concurrency": CONCURRENCY,
        "endpoint": "POST /api/v1/ask",
        "successful_requests": len(successful),
        "errors": REQUESTS - len(successful),
        "request_throughput_per_second": round(len(successful) / elapsed, 2),
        "latency_ms": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "p99": percentile(latencies, 99)},
        "model": "extractive-offline-baseline",
        "storage": "MongoDB-backed retrieval",
    }
    print(json.dumps(result, indent=2))
    if result["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
