import json
import os
import re
from decimal import Decimal
from functools import cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine
from sqlalchemy.pool import NullPool


@cache
def secret(name: str) -> str:
    direct = os.getenv(name)
    if direct:
        return direct
    arn = os.getenv(f"{name}_SECRET_ARN")
    if arn:
        import boto3

        return str(boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"])
    raise RuntimeError(f"Missing configuration for {name}")


@cache
def engine() -> Engine:
    if os.getenv("DATABASE_SECRET_ARN"):
        data = json.loads(secret("DATABASE"))
        url = URL.create(
            "postgresql+psycopg",
            username=data["username"],
            password=data["password"],
            host=os.environ["DATABASE_HOST"],
            port=5432,
            database="mortgageflow",
            query={"sslmode": "verify-full", "sslrootcert": "/var/task/global-bundle.pem"},
        )
        return create_engine(url, poolclass=NullPool)
    local_engine = create_engine(secret("DATABASE_URL"), pool_pre_ping=True)
    if local_engine.dialect.name == "sqlite":
        event.listen(local_engine, "connect", enable_sqlite_foreign_keys)
    return local_engine


def enable_sqlite_foreign_keys(connection, _record) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


@cache
def threshold() -> Decimal:
    value = Decimal(os.getenv("DEMO_DTI_THRESHOLD", "43.00"))
    if not value.is_finite() or not 0 < value <= 100 or value != value.quantize(Decimal(".01")):
        raise RuntimeError("DEMO_DTI_THRESHOLD must be between 0 and 100 with two decimal places")
    return value


@cache
def identities() -> dict[str, tuple[str, str]]:
    data = json.loads(secret("API_IDENTITIES"))
    result = {}
    for actor, record in data.items():
        role, token = record["role"], record["token"]
        if (
            not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", actor)
            or role not in {"applicant", "reviewer"}
            or not re.fullmatch(r"[a-zA-Z0-9._~-]{24,256}", token)
            or token in result
        ):
            raise RuntimeError("Invalid API identity configuration")
        result[token] = (actor, role)
    return result
