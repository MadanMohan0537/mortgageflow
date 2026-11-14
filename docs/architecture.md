# MortgageFlow architecture

Educational simulation only. Synthetic data; demo validation rules are **not** lending decisions.

## Request path

```text
Client (curl / Swagger / Postman)
        |
        v
 FastAPI (/v1/...)  ---- service / validation layer ---- PostgreSQL
        |
        +---- pre-signed S3 PUT URL
                    |
                    v
              S3 ObjectCreated
                    |
                    v
           Document Lambda worker ---- PostgreSQL metadata (idempotent)
                    |
                    v
              CloudWatch Logs / Alarms
```

## Status lifecycle

```text
DRAFT --> SUBMITTED --> IN_REVIEW --> COMPLETED
                |            |
                +--> NEEDS_INFO <--+
```

## Database ER (logical)

```text
applications 1──* validation_results
applications 1──* documents
applications 1──* audit_events
```

| Table | Purpose |
| --- | --- |
| `applications` | Lifecycle + synthetic financial fields |
| `validation_results` | DTI + demo-rule flags + `rules_version` |
| `documents` | S3 key/metadata; `upload_event_id` UNIQUE for dedupe |
| `audit_events` | Actor, action, correlation_id, timestamp |

## Deployment tradeoff

| Approach | Pros | Cons |
| --- | --- | --- |
| **Lambda + API Gateway + Mangum** (chosen in `infra/`) | Low idle cost, fits portfolio budgets, SAM packaging | Cold starts; DB connection management needs care |
| ECS/Fargate | Persistent connections, simpler long-running workers | Higher baseline cost for a student demo |

Local development uses Docker Compose (API + PostgreSQL + LocalStack S3) without AWS spend.
