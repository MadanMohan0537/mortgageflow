from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("annual_income > 0 AND requested_amount > 0"),
        CheckConstraint("monthly_debt >= 0 AND housing_payment >= 0"),
        Index("ix_applications_status_created", "status", "created_at"),
        Index("ix_applications_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(80))
    applicant_alias: Mapped[str] = mapped_column(String(80))
    annual_income: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    monthly_debt: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    housing_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Validation(Base):
    __tablename__ = "validation_results"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    dti_ratio: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    flags: Mapped[list[dict[str, str]]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    rules_version: Mapped[str] = mapped_column(String(24))
    threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    s3_key: Mapped[str] = mapped_column(String(240), unique=True)
    mime_type: Mapped[str] = mapped_column(String(64))
    expected_size: Mapped[int]
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    upload_event_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    failure_reason: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    correlation_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
