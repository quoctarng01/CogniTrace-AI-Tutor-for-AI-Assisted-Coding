#!/usr/bin/env python3
"""Workstream 10 — Load test for the trace-execution path.

Fires N concurrent `POST /api/traces/run` requests against a running
CogniTrace stack and reports p50 / p95 latency. Used before the empirical
study to verify the system holds up under load.

Usage:
    python scripts/load_test_traces.py [--concurrency 50] [--requests 100] [--base-url http://localhost:8000]

Pre-requisites:
    - The FastAPI backend is running (e.g. via `uvicorn app.main:app --port 8000`).
    - For authenticated requests, set the COGNITRACE_TEST_TOKEN env var;
      otherwise the test uses an anonymous run which is rate-limited.

The script is intentionally minimal — no external dependencies beyond
`httpx` (already a backend dep). Output is plain text so it's easy to
redirect to a log file.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from typing import Any

import httpx


# ── Sample code to trace ──────────────────────────────────────────
# Keep it short — the goal is to measure the round trip, not the trace itself.
SAMPLE_CODE = "x = 1\ny = x + 1\nz = y * 2\nprint(z)"


async def fire_one(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> tuple[float, int]:
    """Fire a single POST and return (latency_seconds, status_code)."""
    started = time.monotonic()
    try:
        resp = await client.post(
            url,
            json={"code": SAMPLE_CODE, "language": "python", "initial_namespace": {}},
            headers=headers,
            timeout=30.0,
        )
        return time.monotonic() - started, resp.status_code
    except httpx.HTTPError:
        return time.monotonic() - started, 0


async def run_load_test(base_url: str, total: int, concurrency: int, token: str | None) -> None:
    """Spawn `concurrency` tasks, each firing `total // concurrency` requests."""
    url = f"{base_url.rstrip('/')}/api/traces/run"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Use one shared client per worker; the default limits work for our test load.
    limits = httpx.Limits(max_connections=concurrency + 5, max_keepalive_connections=concurrency)

    sem = asyncio.Semaphore(concurrency)

    async def worker(client: httpx.AsyncClient) -> list[tuple[float, int]]:
        out: list[tuple[float, int]] = []
        for _ in range(total // concurrency):
            async with sem:
                out.append(await fire_one(client, url, headers))
        return out

    started = time.monotonic()
    async with httpx.AsyncClient(limits=limits) as client:
        results = await asyncio.gather(*(worker(client) for _ in range(concurrency)))
    elapsed = time.monotonic() - started

    flat = [r for sub in results for r in sub]
    if not flat:
        print("no requests were fired", file=sys.stderr)
        sys.exit(1)

    latencies = [r[0] for r in flat]
    statuses = [r[1] for r in flat]
    ok = sum(1 for s in statuses if 200 <= s < 300)
    rate_limited = sum(1 for s in statuses if s == 429)
    errored = sum(1 for s in statuses if s == 0 or s >= 500)

    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
    p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies)
    throughput = len(flat) / elapsed if elapsed > 0 else 0.0

    print("=" * 60)
    print(f"CogniTrace trace-execution load test")
    print("=" * 60)
    print(f"base_url:          {base_url}")
    print(f"endpoint:          POST /api/traces/run")
    print(f"concurrency:       {concurrency}")
    print(f"requests sent:     {len(flat)}")
    print(f"total wall time:   {elapsed:.2f}s")
    print(f"throughput:        {throughput:.1f} req/s")
    print("-" * 60)
    print(f"p50 latency:       {p50 * 1000:.0f} ms")
    print(f"p95 latency:       {p95 * 1000:.0f} ms")
    print(f"p99 latency:       {p99 * 1000:.0f} ms")
    print(f"max latency:       {max(latencies) * 1000:.0f} ms")
    print("-" * 60)
    print(f"successful (2xx):  {ok}")
    print(f"rate-limited (429):{rate_limited}")
    print(f"errored (5xx/0):   {errored}")
    print("=" * 60)

    # Acceptance per the hardening plan:
    # "prints p50/p95 latency under 50 concurrent traces" — non-blocking.
    if p95 > 6.0:
        print(f"WARNING: p95 {p95 * 1000:.0f}ms exceeds 6000ms healthy threshold")
        sys.exit(2)
    if errored > 0:
        print(f"WARNING: {errored} requests errored (5xx / network)")
        sys.exit(3)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "")
    p.add_argument("--base-url", default=os.environ.get("COGNITRACE_BASE_URL", "http://localhost:8000"))
    p.add_argument("--concurrency", type=int, default=50)
    p.add_argument("--requests", type=int, default=100)
    p.add_argument("--token", default=os.environ.get("COGNITRACE_TEST_TOKEN"))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.requests < args.concurrency:
        print(f"--requests ({args.requests}) must be >= --concurrency ({args.concurrency})")
        sys.exit(1)
    asyncio.run(run_load_test(args.base_url, args.requests, args.concurrency, args.token))


if __name__ == "__main__":
    main()
