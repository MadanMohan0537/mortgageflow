from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Status(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    NEEDS_INFO = "NEEDS_INFO"
    COMPLETED = "COMPLETED"


Alias = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")]
Positive = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Nonnegative = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Principal = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DOCUMENT_TYPES = {".pdf": "application/pdf", ".txt": "text/plain"}


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ApplicationInput(Schema):
    applicant_alias: Alias
    annual_income: Positive
    monthly_debt: Nonnegative
    housing_payment: Nonnegative
    requested_amount: Principal

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "applicant_alias": "demo-user-001",
                    "annual_income": "90000.00",
                    "monthly_debt": "800.00",
                    "housing_payment": "1800.00",
                    "requested_amount": "250000.00",
                }
            ]
        }
    )


class ApplicationPatch(Schema):
    applicant_alias: Alias | None = None
    annual_income: Positive | None = None
    monthly_debt: Nonnegative | None = None
    housing_payment: Nonnegative | None = None
    requested_amount: Principal | None = None

    @model_validator(mode="after")
    def require_updates(self):
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError(
                "Supply at least one field and omit fields that should remain unchanged"
            )
        return self


class ApplicationView(ApplicationInput):
    id: UUID
    status: Status
    created_at: datetime
    updated_at: datetime


class Page(Schema):
    items: list[ApplicationView]
    limit: int
    offset: int
    total: int


class ValidationView(Schema):
    id: UUID
    dti_ratio: Decimal
    threshold: Decimal
    flags: list[dict[str, str]]
    rules_version: str
    checked_at: datetime

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class UploadInput(Schema):
    filename: Annotated[str, Field(min_length=1, max_length=120)]
    mime_type: Literal["application/pdf", "text/plain"]
    size_bytes: Annotated[int, Field(strict=True, gt=0, le=MAX_UPLOAD_BYTES)]


class UploadView(Schema):
    document_id: UUID
    url: str
    headers: dict[str, str]
    expires_in: int


class DocumentView(Schema):
    id: UUID
    status: Literal["PENDING", "PROCESSED", "REJECTED"]
    mime_type: str
    failure_reason: str | None


class StatusView(Schema):
    status: Status
    outstanding_tasks: list[str]
    documents: list[DocumentView]


class ReviewInput(Schema):
    status: Literal[Status.IN_REVIEW, Status.NEEDS_INFO, Status.COMPLETED]


class AuditView(Schema):
    actor_id: str
    action: str
    correlation_id: str
    occurred_at: datetime
