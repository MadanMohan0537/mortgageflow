# Security & privacy statement

MortgageFlow is a **fictional educational simulation**.

- Use **synthetic** applicant aliases and amounts only.
- Do **not** upload real SSNs, government IDs, bank statements, or loan documents.
- Validation flags (for example `REVIEW_DTI`) are **example rule outcomes**, not approvals or denials.
- API access requires an `X-API-Key` header; optional JWT bearer / `X-Actor-Id` identifies the actor for audit events.
- S3 buckets are private; uploads use short-lived pre-signed URLs with extension and size checks.
- Never commit `.env` files or AWS credentials. Prefer Secrets Manager / SSM in cloud environments.
- Tear down idle AWS resources and keep budget alerts enabled.
