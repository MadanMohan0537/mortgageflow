"""Application settings loaded from environment variables."""

from functools import lru_cache
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MortgageFlow"
    app_env: str = "local"
    api_prefix: str = "/v1"
    log_level: str = "INFO"
    correlation_header: str = "X-Correlation-ID"

    api_key: str = "dev-api-key-change-me"
    jwt_secret: str = "dev-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    database_url: str = (
        "postgresql+psycopg2://mortgageflow:mortgageflow@localhost:5432/mortgageflow"
    )

    dti_review_threshold: Decimal = Field(default=Decimal("43.00"))
    rules_version: str = "demo-rules-v1"

    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    s3_bucket: str = "mortgageflow-docs-local"
    s3_endpoint_url: str | None = "http://localhost:4566"
    presigned_url_expires_seconds: int = 300
    max_document_bytes: int = 1_048_576
    allowed_document_extensions: str = ".pdf,.txt"

    @property
    def allowed_extensions(self) -> set[str]:
        return {
            ext.strip().lower()
            for ext in self.allowed_document_extensions.split(",")
            if ext.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
