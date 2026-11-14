"""Pydantic schemas for mortgage applications and related resources."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ApplicationStatus, DocumentStatus


class ApplicationCreate(BaseModel):
    applicant_alias: str = Field(min_length=1, max_length=80)
    annual_income: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    monthly_debt: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    housing_payment: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    requested_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)

    @field_validator(
        "annual_income",
        "monthly_debt",
        "housing_payment",
        "requested_amount",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, value: Any) -> Any:
        if isinstance(value, str):
            return Decimal(value)
        return value


class ApplicationUpdate(BaseModel):
    applicant_alias: str | None = Field(default=None, min_length=1, max_length=80)
    annual_income: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    monthly_debt: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    housing_payment: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    requested_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=2
    )
    status: ApplicationStatus | None = None

    @field_validator(
        "annual_income",
        "monthly_debt",
        "housing_payment",
        "requested_amount",
        mode="before",
    )
    @classmethod
    def coerce_decimal(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            return Decimal(value)
        return value


class ApplicationCreated(BaseModel):
    id: UUID
    status: ApplicationStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationRead(BaseModel):
    id: UUID
    applicant_alias: str
    annual_income: Decimal
    monthly_debt: Decimal
    housing_payment: Decimal
    requested_amount: Decimal
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ValidationFlag(BaseModel):
    code: str
    message: str
    severity: str = "info"


class ValidationResultRead(BaseModel):
    id: UUID
    application_id: UUID
    dti_ratio: Decimal
    flags: list[dict[str, Any]]
    rules_version: str
    explanation: str
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(gt=0)


class DocumentUploadUrlResponse(BaseModel):
    document_id: UUID
    upload_url: str
    s3_key: str
    expires_in_seconds: int
    status: DocumentStatus


class DocumentRead(BaseModel):
    id: UUID
    application_id: UUID
    s3_key: str
    mime_type: str
    original_filename: str
    status: DocumentStatus
    size_bytes: int | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationStatusResponse(BaseModel):
    id: UUID
    status: ApplicationStatus
    outstanding_tasks: list[str]
    latest_validation: ValidationResultRead | None = None
    documents: list[DocumentRead] = Field(default_factory=list)


class ReviewStatusUpdate(BaseModel):
    status: ApplicationStatus
    note: str | None = Field(default=None, max_length=500)
