import hashlib
import json
import logging
from pathlib import PurePath
from time import perf_counter
from urllib.parse import unquote_plus

from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import engine
from app.models import Document
from app.repository import audit
from app.schemas import DOCUMENT_TYPES, MAX_UPLOAD_BYTES
from app.storage import bucket, s3

logger = logging.getLogger("mortgageflow.worker")
logger.setLevel(logging.INFO)


def process(record: dict, correlation: str) -> None:
    if record["eventSource"] != "aws:s3" or not record["eventName"].startswith("ObjectCreated:"):
        return
    event = record["s3"]
    if event["bucket"]["name"] != bucket():
        return
    obj = event["object"]
    key = unquote_plus(obj["key"])
    event_id = hashlib.sha256(f"{bucket()}:{key}:{obj['sequencer']}".encode()).hexdigest()
    etag = '"' + obj["eTag"].strip('"') + '"'
    start = perf_counter()
    with Session(engine()) as db, db.begin():
        document = db.scalar(select(Document).where(Document.s3_key == key).with_for_update())
        if document is None or document.status != "PENDING":
            return
        reason: str | None = None
        try:
            head = s3().head_object(Bucket=bucket(), Key=key, IfMatch=etag)
        except ClientError as exc:
            if exc.response["ResponseMetadata"]["HTTPStatusCode"] not in {404, 412}:
                raise
            reason = "Uploaded object is missing or has changed"
        else:
            if (
                head["ContentType"] != document.mime_type
                or DOCUMENT_TYPES.get(PurePath(key).suffix) != document.mime_type
            ):
                reason = "Unexpected content type"
            elif not 0 < head["ContentLength"] <= MAX_UPLOAD_BYTES or (
                head["ContentLength"] != document.expected_size
            ):
                reason = "Unexpected content length"

        document.status = "REJECTED" if reason else "PROCESSED"
        document.failure_reason = reason
        document.upload_event_id = event_id
        audit(db, document.application_id, "worker", f"DOCUMENT_{document.status}", correlation)
        outcome = document.status
        app_id = str(document.application_id)
    logger.info(
        json.dumps(
            {
                "event": "document_processed",
                "application_id": app_id,
                "correlation_id": correlation,
                "outcome": outcome,
                "duration_ms": round((perf_counter() - start) * 1000, 2),
            }
        )
    )


def handler(event, context):
    failures = 0
    correlation = context.aws_request_id
    for record in event.get("Records", []):
        try:
            process(record, correlation)
        except (KeyError, TypeError, AttributeError):
            logger.warning("malformed_s3_notification correlation_id=%s", correlation)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.error(
                "document_processing_failure correlation_id=%s type=%s",
                correlation,
                type(exc).__name__,
            )
    if failures:
        raise RuntimeError(f"{failures} document event(s) require retry")
