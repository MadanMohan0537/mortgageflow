from types import SimpleNamespace
from uuid import uuid4

import pytest
from botocore.stub import Stubber
from conftest import ALICE
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.config import engine
from app.models import Document
from workers import document_worker

UPLOAD = {"filename": "dummy.txt", "mime_type": "text/plain", "size_bytes": 10}
BUCKET = "synthetic-test-bucket"


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    storage.s3.cache_clear()
    yield storage.s3()
    storage.s3.cache_clear()


def notification(key):
    return {
        "Records": [
            {
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": BUCKET},
                    "object": {"key": key, "eTag": "abcdef", "sequencer": "12345"},
                },
            }
        ]
    }


def run_worker(event):
    return document_worker.handler(event, SimpleNamespace(aws_request_id=str(uuid4())))


@pytest.mark.parametrize(
    ("content_type", "length", "outcome"),
    [
        ("text/plain", 10, "PROCESSED"),
        ("application/pdf", 10, "REJECTED"),
        ("text/plain", 11, "REJECTED"),
    ],
)
def test_upload(client, application, s3, content_type, length, outcome):
    path = f"{application}/documents/upload-url"
    assert (
        client.post(path, headers=ALICE, json={**UPLOAD, "filename": "dummy.exe"}).status_code
        == 400
    )
    signed = client.post(path, headers=ALICE, json=UPLOAD)
    assert signed.status_code == 201
    assert signed.json()["headers"]["If-None-Match"] == "*"
    assert (
        "X-Amz-SignedHeaders=content-length%3Bcontent-type%3Bhost%3Bif-none-match"
        in signed.json()["url"]
    )
    with Session(engine()) as db:
        key = db.scalars(select(Document.s3_key)).one()
    params = {"Bucket": BUCKET, "Key": key, "IfMatch": '"abcdef"'}
    with Stubber(s3) as stub:
        stub.add_client_error("head_object", http_status_code=503, expected_params=params)
        with pytest.raises(RuntimeError):
            run_worker(notification(key))
        assert (
            client.get(f"{application}/status", headers=ALICE).json()["documents"][0]["status"]
            == "PENDING"
        )
        stub.add_response(
            "head_object", {"ContentType": content_type, "ContentLength": length}, params
        )
        run_worker(notification(key))
        run_worker(notification(key))
        run_worker({"Records": [{}, notification("unknown")["Records"][0]]})
        stub.assert_no_pending_responses()
    assert (
        client.get(f"{application}/status", headers=ALICE).json()["documents"][0]["status"]
        == outcome
    )
    logs = client.get(f"{application}/audit", headers=ALICE).json()
    assert sum(item["action"] == f"DOCUMENT_{outcome}" for item in logs) == 1
