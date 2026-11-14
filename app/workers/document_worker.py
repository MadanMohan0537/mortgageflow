"""S3 ObjectCreated document processing worker (Lambda handler).

Idempotent: uses S3 event ID (or object etag+key) as upload_event_id UNIQUE.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.models.enums import DocumentStatus
from app.repositories.applications import ApplicationRepository

configure_logging()
logger = get_logger(__name__)


def _session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    database_url = os.getenv("DATABASE_URL", settings.database_url)
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _allowed_extension(filename: str, allowed: set[str]) -> bool:
    return PurePosixPath(filename).suffix.lower() in allowed


def process_s3_record(db: Session, record: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    repo = ApplicationRepository(db)

    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    size = int(record["s3"]["object"].get("size") or 0)
    event_id = (
        record.get("responseElements", {}).get("x-amz-request-id")
        or record.get("eventID")
        or f"{bucket}:{key}:{record['s3']['object'].get('eTag', 'na')}"
    )

    logger.info(
        "Processing S3 object bucket=%s key=%s event_id=%s size=%s",
        bucket,
        key,
        event_id,
        size,
    )

    existing = repo.get_document_by_event_id(event_id)
    if existing:
        logger.info("Duplicate event ignored for document %s", existing.id)
        return {
            "status": "duplicate",
            "document_id": str(existing.id),
            "event_id": event_id,
        }

    document = repo.get_document_by_s3_key(key)
    if not document:
        logger.warning("No document metadata for key=%s — creating orphan reject", key)
        # Orphan uploads are rejected without attaching to an application.
        return {
            "status": "rejected",
            "reason": "unknown_object_key",
            "event_id": event_id,
        }

    if not _allowed_extension(document.original_filename, settings.allowed_extensions):
        document.status = DocumentStatus.REJECTED.value
        document.upload_event_id = event_id
        document.rejection_reason = "Unsupported file extension"
        document.size_bytes = size
        repo.add_audit(
            application_id=document.application_id,
            actor_id="document-worker",
            action="DOCUMENT_REJECTED",
            correlation_id=event_id,
            detail={"reason": document.rejection_reason, "s3_key": key},
        )
        db.commit()
        return {
            "status": "rejected",
            "document_id": str(document.id),
            "reason": document.rejection_reason,
        }

    if size <= 0 or size > settings.max_document_bytes:
        document.status = DocumentStatus.REJECTED.value
        document.upload_event_id = event_id
        document.rejection_reason = "File size out of allowed range"
        document.size_bytes = size
        repo.add_audit(
            application_id=document.application_id,
            actor_id="document-worker",
            action="DOCUMENT_REJECTED",
            correlation_id=event_id,
            detail={"reason": document.rejection_reason, "size": size},
        )
        db.commit()
        return {
            "status": "rejected",
            "document_id": str(document.id),
            "reason": document.rejection_reason,
        }

    document.status = DocumentStatus.PROCESSED.value
    document.upload_event_id = event_id
    document.size_bytes = size
    document.rejection_reason = None
    repo.add_audit(
        application_id=document.application_id,
        actor_id="document-worker",
        action="DOCUMENT_PROCESSED",
        correlation_id=event_id,
        detail={"s3_key": key, "size": size},
    )
    db.commit()
    return {
        "status": "processed",
        "document_id": str(document.id),
        "application_id": str(document.application_id),
        "event_id": event_id,
    }


def handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    """AWS Lambda entrypoint for S3 notifications."""
    SessionLocal = _session_factory()
    results = []
    with SessionLocal() as db:
        for record in event.get("Records", []):
            try:
                results.append(process_s3_record(db, record))
            except Exception as exc:  # noqa: BLE001 — report per-record failure
                logger.exception("Failed processing record: %s", exc)
                db.rollback()
                results.append({"status": "failed", "error": str(exc)})
    return {"ok": True, "results": results}


def local_invoke(event_path: str) -> None:
    with open(event_path, encoding="utf-8") as fh:
        event = json.load(fh)
    print(json.dumps(handler(event), indent=2, default=str))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.workers.document_worker <event.json>")
        raise SystemExit(1)
    local_invoke(sys.argv[1])
