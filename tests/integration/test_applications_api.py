"""API integration tests for application lifecycle."""

from __future__ import annotations

import uuid


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_application_201(client, auth_headers, sample_payload):
    response = client.post(
        "/v1/applications", json=sample_payload, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert "id" in body
    assert "created_at" in body
    assert response.headers.get("X-Correlation-ID")


def test_create_missing_income_422(client, auth_headers, sample_payload):
    payload = dict(sample_payload)
    del payload["annual_income"]
    response = client.post("/v1/applications", json=payload, headers=auth_headers)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["correlation_id"]


def test_create_negative_debt_422(client, auth_headers, sample_payload):
    payload = dict(sample_payload)
    payload["monthly_debt"] = "-10.00"
    response = client.post("/v1/applications", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_auth_failure_401(client, sample_payload):
    response = client.post("/v1/applications", json=sample_payload)
    assert response.status_code == 401


def test_get_unknown_uuid_404(client, auth_headers):
    missing = uuid.uuid4()
    response = client.get(f"/v1/applications/{missing}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_get_and_list(client, auth_headers, sample_payload):
    created = client.post(
        "/v1/applications", json=sample_payload, headers=auth_headers
    ).json()
    got = client.get(f"/v1/applications/{created['id']}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["applicant_alias"] == "demo-user-001"

    listed = client.get(
        "/v1/applications",
        params={"status": "DRAFT", "page": 1, "page_size": 10},
        headers=auth_headers,
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    assert any(item["id"] == created["id"] for item in body["items"])


def test_validate_and_submit(client, auth_headers, sample_payload):
    created = client.post(
        "/v1/applications", json=sample_payload, headers=auth_headers
    ).json()
    app_id = created["id"]

    validated = client.post(
        f"/v1/applications/{app_id}/validate", headers=auth_headers
    )
    assert validated.status_code == 200
    assert validated.json()["dti_ratio"] == "34.67"

    submitted = client.post(
        f"/v1/applications/{app_id}/submit", headers=auth_headers
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "SUBMITTED"


def test_submit_from_completed_409(client, auth_headers, sample_payload):
    created = client.post(
        "/v1/applications", json=sample_payload, headers=auth_headers
    ).json()
    app_id = created["id"]
    client.post(f"/v1/applications/{app_id}/submit", headers=auth_headers)
    client.post(
        f"/v1/applications/{app_id}/review",
        json={"status": "IN_REVIEW"},
        headers={**auth_headers, "X-Actor-Id": "reviewer-1"},
    )
    client.post(
        f"/v1/applications/{app_id}/review",
        json={"status": "COMPLETED"},
        headers={**auth_headers, "X-Actor-Id": "reviewer-1"},
    )
    response = client.post(f"/v1/applications/{app_id}/submit", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


def test_patch_invalid_transition_409(client, auth_headers, sample_payload):
    created = client.post(
        "/v1/applications", json=sample_payload, headers=auth_headers
    ).json()
    response = client.patch(
        f"/v1/applications/{created['id']}",
        json={"status": "COMPLETED"},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_status_endpoint(client, auth_headers, sample_payload):
    created = client.post(
        "/v1/applications", json=sample_payload, headers=auth_headers
    ).json()
    response = client.get(
        f"/v1/applications/{created['id']}/status", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRAFT"
    assert "Submit application" in body["outstanding_tasks"]
