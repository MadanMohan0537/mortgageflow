"""Document upload URL and worker idempotency tests."""

from __future__ import annotations

from app.workers.document_worker import process_s3_record
from app.repositories.applications import ApplicationRepository
from app.models.enums import DocumentStatus


def _create_app(client, auth_headers, sample_payload):
    return client.post(
        "/v1/applications", json=sample_payload, headers=auth_headers
    ).json()


def test_upload_url_success(client, auth_headers, sample_payload):
    app = _create_app(client, auth_headers, sample_payload)
    response = client.post(
        f"/v1/applications/{app['id']}/documents/upload-url",
        json={
            "filename": "paystub.txt",
            "mime_type": "text/plain",
            "size_bytes": 128,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING_UPLOAD"
    assert body["upload_url"]
    assert "applications/" in body["s3_key"]


def test_upload_unsupported_type_rejected(client, auth_headers, sample_payload):
    app = _create_app(client, auth_headers, sample_payload)
    response = client.post(
        f"/v1/applications/{app['id']}/documents/upload-url",
        json={
            "filename": "malware.exe",
            "mime_type": "application/octet-stream",
            "size_bytes": 128,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "DOMAIN_VALIDATION"


def test_worker_processes_and_dedupes(client, auth_headers, sample_payload, db_session):
    app = _create_app(client, auth_headers, sample_payload)
    issued = client.post(
        f"/v1/applications/{app['id']}/documents/upload-url",
        json={
            "filename": "w2.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 512,
        },
        headers=auth_headers,
    ).json()

    record = {
        "eventID": "evt-001",
        "responseElements": {"x-amz-request-id": "req-001"},
        "s3": {
            "bucket": {"name": "mortgageflow-docs-test"},
            "object": {
                "key": issued["s3_key"],
                "size": 512,
                "eTag": "abc",
            },
        },
    }

    first = process_s3_record(db_session, record)
    assert first["status"] == "processed"

    repo = ApplicationRepository(db_session)
    doc = repo.get_document_by_s3_key(issued["s3_key"])
    assert doc is not None
    assert doc.status == DocumentStatus.PROCESSED.value
    assert doc.upload_event_id == "req-001"

    second = process_s3_record(db_session, record)
    assert second["status"] == "duplicate"
