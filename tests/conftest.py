"""Shared pytest fixtures — in-memory SQLite for fast local tests."""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from decimal import Decimal

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Force deterministic test settings before app import
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("S3_BUCKET", "mortgageflow-docs-test")
os.environ.setdefault("S3_ENDPOINT_URL", "")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.schemas.application import ApplicationCreate

get_settings.cache_clear()


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(
        bind=db_engine, autocommit=False, autoflush=False, class_=Session
    )
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def s3_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="mortgageflow-docs-test")
        yield client


@pytest.fixture()
def client(db_session, s3_bucket) -> Generator[TestClient, None, None]:
    def _override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {
        "X-API-Key": "test-api-key",
        "X-Actor-Id": "test-applicant",
        "X-Correlation-ID": str(uuid.uuid4()),
    }


@pytest.fixture()
def sample_payload() -> dict:
    return {
        "applicant_alias": "demo-user-001",
        "annual_income": "90000.00",
        "monthly_debt": "800.00",
        "housing_payment": "1800.00",
        "requested_amount": "250000.00",
    }


@pytest.fixture()
def sample_create() -> ApplicationCreate:
    return ApplicationCreate(
        applicant_alias="demo-user-001",
        annual_income=Decimal("90000.00"),
        monthly_debt=Decimal("800.00"),
        housing_payment=Decimal("1800.00"),
        requested_amount=Decimal("250000.00"),
    )
