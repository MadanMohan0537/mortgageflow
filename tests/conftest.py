import json
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import engine, identities, secret, threshold
from app.main import app

ALICE = {"Authorization": "Bearer test-applicant-alice-token-0001"}
BOB = {"Authorization": "Bearer test-applicant-bobby-token-0001"}
REVIEW = {"Authorization": "Bearer test-reviewer-token-0000000001"}
EXAMPLE = {
    "applicant_alias": "synthetic-001",
    "annual_income": "90000.00",
    "monthly_debt": "800.00",
    "housing_payment": "1800.00",
    "requested_amount": "250000.00",
}


@pytest.fixture(scope="session")
def migrated(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"
    patch.setenv("DATABASE_URL", url)
    patch.setenv("DEMO_DTI_THRESHOLD", "43.00")
    patch.setenv("DOCUMENT_BUCKET", "synthetic-test-bucket")
    patch.setenv(
        "API_IDENTITIES",
        json.dumps(
            {
                "alice": {"role": "applicant", "token": ALICE["Authorization"].split()[1]},
                "bob": {"role": "applicant", "token": BOB["Authorization"].split()[1]},
                "reviewer": {"role": "reviewer", "token": REVIEW["Authorization"].split()[1]},
            }
        ),
    )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        yield config
    finally:
        command.downgrade(config, "base")
        engine().dispose()
        for cached in (engine, identities, secret, threshold):
            cached.cache_clear()
        patch.undo()


@pytest.fixture
def client(migrated):
    with engine().begin() as conn:
        for table in ("audit_events", "documents", "validation_results", "applications"):
            conn.execute(text(f"DELETE FROM {table}"))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def application(client):
    response = client.post("/v1/applications", headers=ALICE, json=EXAMPLE)
    assert response.status_code == 201, response.text
    return f"/v1/applications/{response.json()['id']}"
