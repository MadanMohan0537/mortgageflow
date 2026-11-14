"""Database access for applications and related entities."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Application, AuditEvent, Document, ValidationResult
from app.models.enums import ApplicationStatus, DocumentStatus


class ApplicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **fields: Any) -> Application:
        application = Application(id=uuid.uuid4(), **fields)
        self.db.add(application)
        self.db.flush()
        return application

    def get(self, application_id: uuid.UUID) -> Application | None:
        return self.db.get(Application, application_id)

    def get_with_relations(self, application_id: uuid.UUID) -> Application | None:
        stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.validation_results),
                selectinload(Application.documents),
            )
        )
        return self.db.scalars(stmt).first()

    def list(
        self,
        *,
        status: ApplicationStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Application], int]:
        filters = []
        if status is not None:
            filters.append(Application.status == status.value)

        count_stmt = select(func.count()).select_from(Application)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = int(self.db.scalar(count_stmt) or 0)

        stmt: Select[tuple[Application]] = (
            select(Application)
            .order_by(Application.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if filters:
            stmt = stmt.where(*filters)
        items = list(self.db.scalars(stmt).all())
        return items, total

    def add_audit(
        self,
        *,
        application_id: uuid.UUID,
        actor_id: str,
        action: str,
        correlation_id: str,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid.uuid4(),
            application_id=application_id,
            actor_id=actor_id,
            action=action,
            correlation_id=correlation_id,
            detail=detail,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def add_validation(
        self,
        *,
        application_id: uuid.UUID,
        dti_ratio: Decimal,
        flags: list[dict[str, Any]],
        rules_version: str,
        explanation: str,
    ) -> ValidationResult:
        result = ValidationResult(
            id=uuid.uuid4(),
            application_id=application_id,
            dti_ratio=dti_ratio,
            flags=flags,
            rules_version=rules_version,
            explanation=explanation,
        )
        self.db.add(result)
        self.db.flush()
        return result

    def create_document(
        self,
        *,
        application_id: uuid.UUID,
        s3_key: str,
        mime_type: str,
        original_filename: str,
        size_bytes: int | None = None,
        status: DocumentStatus = DocumentStatus.PENDING_UPLOAD,
    ) -> Document:
        document = Document(
            id=uuid.uuid4(),
            application_id=application_id,
            s3_key=s3_key,
            mime_type=mime_type,
            original_filename=original_filename,
            size_bytes=size_bytes,
            status=status.value,
        )
        self.db.add(document)
        self.db.flush()
        return document

    def get_document_by_s3_key(self, s3_key: str) -> Document | None:
        stmt = select(Document).where(Document.s3_key == s3_key)
        return self.db.scalars(stmt).first()

    def get_document_by_event_id(self, upload_event_id: str) -> Document | None:
        stmt = select(Document).where(Document.upload_event_id == upload_event_id)
        return self.db.scalars(stmt).first()
