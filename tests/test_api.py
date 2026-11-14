from uuid import uuid4

import pytest
from conftest import ALICE, BOB, EXAMPLE, REVIEW
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import engine
from app.models import Application, AuditEvent


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
    assert client.get("/openapi.json").status_code == 200


def test_scope_and_pagination(client, application):
    assert client.get(application).status_code == 401
    assert client.get(application, headers=BOB).status_code == 404
    assert client.get(application, headers=REVIEW).status_code == 200
    assert client.get(f"/v1/applications/{uuid4()}", headers=ALICE).status_code == 404
    assert client.get("/v1/applications", headers=BOB).json()["total"] == 0
    assert client.post("/v1/applications", headers=ALICE, json=EXAMPLE).status_code == 201
    result = client.get("/v1/applications?status=DRAFT&limit=1&offset=1", headers=ALICE).json()
    assert result["total"] == 2
    assert len(result["items"]) == 1
    assert client.get("/v1/applications?status=COMPLETED", headers=ALICE).json()["total"] == 0


@pytest.mark.parametrize(
    "data",
    [
        {key: value for key, value in EXAMPLE.items() if key != "annual_income"},
        {**EXAMPLE, "monthly_debt": "-1"},
        {**EXAMPLE, "annual_income": "0"},
        {**EXAMPLE, "annual_income": "1.001"},
        {**EXAMPLE, "ssn": "synthetic-test-value"},
    ],
)
def test_invalid_payload(client, data):
    response = client.post("/v1/applications", headers=ALICE, json=data)
    assert response.status_code == 422
    assert response.json()["fields"]
    assert "synthetic-test-value" not in response.text
    assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]


def test_workflow(client, application):
    validate = client.post(f"{application}/validate", headers=ALICE)
    assert validate.json()["dti_ratio"] == "34.67"
    assert validate.json()["rules_version"] == "demo-1"
    assert client.patch(application, headers=ALICE, json={}).status_code == 422
    assert client.patch(application, headers=ALICE, json={"monthly_debt": None}).status_code == 422
    assert (
        client.patch(application, headers=ALICE, json={"monthly_debt": "2000"}).status_code == 200
    )
    assert (
        client.post(f"{application}/validate", headers=REVIEW).json()["flags"][0]["code"]
        == "REVIEW_DTI"
    )
    assert (
        client.post(
            f"{application}/review", headers=ALICE, json={"status": "IN_REVIEW"}
        ).status_code
        == 403
    )
    assert client.post(f"{application}/submit", headers=ALICE).json()["status"] == "SUBMITTED"
    assert client.patch(application, headers=ALICE, json={"monthly_debt": "1"}).status_code == 409
    review = f"{application}/review"
    assert client.post(review, headers=REVIEW, json={"status": "COMPLETED"}).status_code == 409
    assert (
        client.post(review, headers=REVIEW, json={"status": "IN_REVIEW"}).json()["status"]
        == "IN_REVIEW"
    )
    assert (
        client.post(review, headers=REVIEW, json={"status": "NEEDS_INFO"}).json()["status"]
        == "NEEDS_INFO"
    )
    assert client.patch(application, headers=ALICE, json={"monthly_debt": "1"}).status_code == 200
    assert client.post(f"{application}/submit", headers=ALICE).json()["status"] == "IN_REVIEW"
    complete = client.post(review, headers=REVIEW, json={"status": "COMPLETED"})
    assert complete.json()["status"] == "COMPLETED"
    assert client.post(f"{application}/submit", headers=ALICE).status_code == 409
    assert client.get(f"{application}/status", headers=ALICE).json()["outstanding_tasks"] == []
    audit = client.get(f"{application}/audit", headers=ALICE).json()
    assert audit[-1]["action"] == "STATUS_COMPLETED"
    assert audit[-1]["correlation_id"] == complete.headers["X-Correlation-ID"]


def test_failed_audit_rolls_back(client):
    def fail(_, __, statement, *args):
        if statement.startswith("INSERT INTO audit_events"):
            raise OperationalError(statement, {}, RuntimeError("private debug info"))

    event.listen(engine(), "before_cursor_execute", fail)
    try:
        response = client.post("/v1/applications", headers=ALICE, json=EXAMPLE)
    finally:
        event.remove(engine(), "before_cursor_execute", fail)
    assert response.status_code == 503
    assert "private debug info" not in response.text
    with Session(engine()) as db:
        assert db.scalar(select(func.count()).select_from(Application)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0


def test_validation_history_is_read_only_and_owner_scoped(client, application):
    history = f"{application}/validations"
    assert client.get(history, headers=ALICE).json() == []
    assert client.get(history, headers=BOB).status_code == 404

    first = client.post(f"{application}/validate", headers=ALICE).json()
    client.patch(application, headers=ALICE, json={"monthly_debt": "2000.00"}).raise_for_status()
    second = client.post(f"{application}/validate", headers=ALICE).json()

    assert client.get(history, headers=REVIEW).json() == [second, first]
    assert client.get(f"{history}?limit=1&offset=1", headers=ALICE).json() == [first]
    assert client.get(f"{history}?limit=101", headers=ALICE).status_code == 422
    audit = client.get(f"{application}/audit", headers=ALICE).json()
    assert sum(event["action"] == "VALIDATION_RECORDED" for event in audit) == 2


def test_foreign_key_rejects_orphan_audit_event(client):
    from sqlalchemy.exc import IntegrityError

    with Session(engine()) as db:
        db.add(
            AuditEvent(
                application_id=uuid4(), actor_id="test", action="TEST", correlation_id=str(uuid4())
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()
