"""Measure a scoped, authenticated list workload against a running synthetic demo."""

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from statistics import median
from time import perf_counter

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.requests < 1 or args.workers < 1:
        parser.error("requests and workers must be positive")
    with httpx.Client(
        base_url=args.base,
        headers={"Authorization": f"Bearer {os.environ['BENCHMARK_TOKEN']}"},
    ) as client:

        def measure(_: int) -> float:
            start = perf_counter()
            client.get("/v1/applications?status=DRAFT&limit=25").raise_for_status()
            return (perf_counter() - start) * 1000

        for index in range(20):
            measure(index)
        with ThreadPoolExecutor(max_workers=args.workers) as threads:
            durations = sorted(threads.map(measure, range(args.requests)))
    print(f"{len(durations)} successful requests at concurrency {args.workers}")
    print(
        f"p50={median(durations):.2f} ms  p95={durations[ceil(len(durations) * 0.95) - 1]:.2f} ms"
    )


if __name__ == "__main__":
    main()
