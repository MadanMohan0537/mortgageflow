# MortgageFlow

Cloud-oriented **mortgage application processing & validation** backend (educational simulation).

Python/FastAPI handles synchronous APIs; PostgreSQL persists applications, validation results, documents, and audit events; S3 + a Lambda-style worker process synthetic document uploads idempotently.

> **Not a credit product.** Use synthetic data only. Demo rules (for example `REVIEW_DTI`) are explanatory flags, not lending decisions.

## Stack

| Layer | Choice |
| --- | --- |
| API | FastAPI + Pydantic v2 |
| DB | PostgreSQL + SQLAlchemy 2 + Alembic |
| Auth | Shared API key (`X-API-Key`) + actor header / JWT |
| Documents | S3 pre-signed PUT + document worker |
| Local AWS | LocalStack S3 |
| Deploy (optional) | AWS SAM (`infra/template.yaml`) + Mangum |
| Quality | PyTest, Ruff, GitHub Actions |

## Architecture

See [docs/architecture.md](docs/architecture.md).

```text
Client → FastAPI → PostgreSQL
              ↘ S3 pre-signed upload → ObjectCreated → Document worker → PostgreSQL
Logs/metrics → CloudWatch (cloud)
```

## Quick start (local)

### Prerequisites

- Python 3.12+
- Docker + Docker Compose (for PostgreSQL + LocalStack)

### 1. Configure

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start dependencies + API

```bash
docker compose up --build
```

API: http://localhost:8000  
OpenAPI: http://localhost:8000/docs  
Health: `GET /health`

### 3. Or run API on the host

```bash
docker compose up -d db localstack
export $(grep -v '^#' .env | xargs)
alembic upgrade head
uvicorn app.main:app --reload
```

### 4. Seed synthetic samples (optional)

```bash
python scripts/seed_synthetic.py
```

## API examples

All application routes require `X-API-Key` (see `.env.example`).

```bash
export API_KEY=dev-api-key-change-me

# Create
curl -s -X POST http://localhost:8000/v1/applications \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Actor-Id: demo-user-001" \
  -d '{
    "applicant_alias": "demo-user-001",
    "annual_income": "90000.00",
    "monthly_debt": "800.00",
    "housing_payment": "1800.00",
    "requested_amount": "250000.00"
  }'

# Validate (DTI example → 34.67%)
curl -s -X POST http://localhost:8000/v1/applications/<id>/validate \
  -H "X-API-Key: $API_KEY"

# Submit
curl -s -X POST http://localhost:8000/v1/applications/<id>/submit \
  -H "X-API-Key: $API_KEY"

# Document upload URL (synthetic .txt / .pdf only)
curl -s -X POST http://localhost:8000/v1/applications/<id>/documents/upload-url \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"filename":"paystub.txt","mime_type":"text/plain","size_bytes":64}'

# Status
curl -s http://localhost:8000/v1/applications/<id>/status \
  -H "X-API-Key: $API_KEY"
```

### Endpoints

| Method | Route | Behavior |
| --- | --- | --- |
| POST | `/v1/applications` | Create → `201`, status `DRAFT` |
| GET | `/v1/applications` | Paginated list; `?status=` filter |
| GET | `/v1/applications/{id}` | Read one |
| PATCH | `/v1/applications/{id}` | Allowlisted edits; `409` on invalid transitions |
| POST | `/v1/applications/{id}/validate` | Store DTI + demo flags |
| POST | `/v1/applications/{id}/submit` | `DRAFT` → `SUBMITTED` |
| POST | `/v1/applications/{id}/documents/upload-url` | Short-lived S3 PUT URL |
| GET | `/v1/applications/{id}/status` | State + outstanding tasks |
| POST | `/v1/applications/{id}/review` | Reviewer status updates |

Structured errors return `code`, `message`, `correlation_id`, and optional `details`.

## Tests

```bash
pytest -q --cov=app --cov-report=term-missing
```

Coverage includes DTI math, status transitions, 201/401/404/409/422 API cases, unsupported uploads, and duplicate S3 event handling.

## Document worker

```bash
python -m app.workers.document_worker scripts/sample_s3_event.json
```

Deduplication uses `documents.upload_event_id` (UNIQUE). Replaying the same S3 notification does not double-process.

## AWS deployment (optional)

1. Enable a budget alert; prefer a dedicated account/project boundary.
2. Store secrets outside git (Secrets Manager / SSM).
3. Deploy with SAM:

```bash
sam build -t infra/template.yaml
sam deploy --guided
```

4. Capture evidence: private bucket settings, Lambda logs, CloudWatch error alarm.
5. **Teardown** idle RDS/Lambda/API Gateway/S3 resources when finished.

See [docs/security-privacy.md](docs/security-privacy.md) and [docs/performance.md](docs/performance.md).

## Repository layout

```text
app/                 FastAPI app, services, repositories, workers
migrations/          Alembic history
tests/               Unit + API/integration tests
infra/               AWS SAM template
scripts/             Seed, Locust, LocalStack init, sample events
docs/                Architecture, security, performance notes
.github/workflows/   CI (lint + tests)
```

## Definition of done (guide alignment)

- [x] Documented REST API with OpenAPI at `/docs`
- [x] PostgreSQL schema + Alembic migration
- [x] Decimal DTI validation + demo flags / `rules_version`
- [x] Status workflow + audit events with correlation IDs
- [x] S3 pre-signed upload + idempotent document worker
- [x] Automated tests (success, invalid input, auth, conflict, duplicate event)
- [x] Docker Compose local stack + CI workflow
- [x] SAM IaC sketch + security/teardown notes

## Known limitations

- Cloud RDS/networking and real IAM least-privilege tuning are left to the deployer’s budget.
- API key auth is intentionally simple for a portfolio demo; swap for Cognito/JWT gateway auth for production-like setups.
- No OCR, credit pulls, or real PII handling by design.
