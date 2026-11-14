"""Replay a notification for an existing synthetic document in local development."""

import sys
from types import SimpleNamespace
from urllib.parse import quote_plus
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.config import engine
from app.models import Document
from app.storage import bucket, s3
from workers.document_worker import handler

if __name__ == "__main__":
    with Session(engine()) as db:
        document = db.get(Document, UUID(sys.argv[1]))
        if document is None:
            raise SystemExit("Unknown document ID")
        key = document.s3_key
    head = s3().head_object(Bucket=bucket(), Key=key)
    event = {
        "Records": [
            {
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": bucket()},
                    "object": {
                        "key": quote_plus(key),
                        "eTag": head["ETag"].strip('"'),
                        "sequencer": head["ETag"],
                    },
                },
            }
        ]
    }
    handler(event, SimpleNamespace(aws_request_id=str(uuid4())))
