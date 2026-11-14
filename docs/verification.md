# Verification and performance

## Test evidence

The local verification used Python 3.12 and PostgreSQL 18.6. The suite passed **22 tests** with **93.84% statement coverage** across the API and worker. Ruff lint, formatting, and mypy passed. The SAM template passed CloudFormation lint in us-east-1.

```text
22 passed
Required test coverage of 85% reached. Total coverage: 93.84%
```

A separate HTTP smoke test used Uvicorn, the same PostgreSQL server, and the Moto S3 emulator. It covered creating a draft, validating the sample (34.67% DTI), submitting, reviewing, uploading with a signed URL, replaying an upload notification twice, receiving one processing audit event, rejecting an unauthenticated read with HTTP 401, and completing review. The AWS stack and the live S3 notification trigger require verification after deployment.

## Local HTTP baseline

The authenticated application-list endpoint returned the first 25 drafts from 200 synthetic draft rows, using the same PostgreSQL dataset throughout. The client and services ran on the same host over loopback. The test used one Uvicorn process, 20 warm-up requests, 300 measured requests, and eight concurrent client threads.

| Requests | Concurrency | p50 | p95 |
|---|---:|---:|---:|
| 300 successful | 8 | 25.64 ms | 36.44 ms |

These measurements include HTTP round-trip time, querying and response serialization. The baseline covers one workload on one host. No tuning claim is made.

With the local API running and a synthetic dataset loaded, repeat the workload with:

```sh
BENCHMARK_TOKEN=demo-applicant-local-token-0001 python -m scripts.benchmark \
  --requests 300 --workers 8
```
