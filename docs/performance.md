# Performance notes

Do not invent metrics for resumes or interviews. Record baselines on the same machine and dataset.

## Suggested local baseline

1. Start the stack: `docker compose up --build`
2. Run Locust:

```bash
locust -f scripts/locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 30s
```

3. Capture p50/p95 for `/health` and `GET /v1/applications`.
4. If list latency grows, inspect `idx_applications_status_created` usage and N+1 queries on status endpoints.

Replace this section with your measured numbers after a real run.
