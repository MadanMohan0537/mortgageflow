"""Application business logic."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import correlation_id_var
from app.models import Application, Document, ValidationResult
from app.models.enums import ApplicationStatus, DocumentStatus
from app.repositories.applications import ApplicationRepository
from app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    DocumentUploadRequest,
)
from app.services.s3 import S3Service
from app.services.status import assert_transition_allowed, can_edit_financial_fields
from app.services.validation import evaluate_application


class ApplicationService:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        s3: S3Service | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.repo = ApplicationRepository(db)
        self.s3 = s3 or S3Service(self.settings)

    def _correlation(self) -> str:
        return correlation_id_var.get() or str(uuid.uuid4())

    def create(self, payload: ApplicationCreate, actor_id: str) -> Application:
        application = self.repo.create(
            applicant_alias=payload.applicant_alias,
            annual_income=payload.annual_income,
            monthly_debt=payload.monthly_debt,
            housing_payment=payload.housing_payment,
            requested_amount=payload.requested_amount,
            status=ApplicationStatus.DRAFT.value,
        )
        self.repo.add_audit(
            application_id=application.id,
            actor_id=actor_id,
            action="APPLICATION_CREATED",
            correlation_id=self._correlation(),
            detail={"status": application.status},
        )
        self.db.commit()
        self.db.refresh(application)
        return application

    def get(self, application_id: uuid.UUID) -> Application:
        application = self.repo.get(application_id)
        if not application:
            raise NotFoundError(f"Application {application_id} not found")
        return application

    def list(
        self,
        *,
        status: ApplicationStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Application], int]:
        return self.repo.list(status=status, page=page, page_size=page_size)

    def update(
        self,
        application_id: uuid.UUID,
        payload: ApplicationUpdate,
        actor_id: str,
    ) -> Application:
        application = self.get(application_id)
        data = payload.model_dump(exclude_unset=True)

        if "status" in data and data["status"] is not None:
            target = ApplicationStatus(data["status"])
            assert_transition_allowed(application.status, target)
            application.status = target.value
            data.pop("status")

        financial_keys = {
            "applicant_alias",
            "annual_income",
            "monthly_debt",
            "housing_payment",
            "requested_amount",
        }
        if financial_keys.intersection(data.keys()):
            if not can_edit_financial_fields(application.status):
                raise ConflictError(
                    f"Cannot edit financial fields while status is {application.status}"
                )
            for key, value in data.items():
                setattr(application, key, value)
        elif data:
            for key, value in data.items():
                setattr(application, key, value)

        self.repo.add_audit(
            application_id=application.id,
            actor_id=actor_id,
            action="APPLICATION_UPDATED",
            correlation_id=self._correlation(),
            detail={"fields": sorted(payload.model_dump(exclude_unset=True).keys())},
        )
        self.db.commit()
        self.db.refresh(application)
        return application

    def validate(
        self, application_id: uuid.UUID, actor_id: str
    ) -> ValidationResult:
        application = self.get(application_id)
        outcome = evaluate_application(
            annual_income=application.annual_income,
            monthly_debt=application.monthly_debt,
            housing_payment=application.housing_payment,
            requested_amount=application.requested_amount,
            settings=self.settings,
        )
        result = self.repo.add_validation(
            application_id=application.id,
            dti_ratio=outcome.dti_ratio,
            flags=outcome.flags,
            rules_version=outcome.rules_version,
            explanation=outcome.explanation,
        )
        self.repo.add_audit(
            application_id=application.id,
            actor_id=actor_id,
            action="APPLICATION_VALIDATED",
            correlation_id=self._correlation(),
            detail={"dti_ratio": str(outcome.dti_ratio), "flags": outcome.flags},
        )
        self.db.commit()
        self.db.refresh(result)
        return result

    def submit(self, application_id: uuid.UUID, actor_id: str) -> Application:
        application = self.get(application_id)
        assert_transition_allowed(application.status, ApplicationStatus.SUBMITTED)

        outcome = evaluate_application(
            annual_income=application.annual_income,
            monthly_debt=application.monthly_debt,
            housing_payment=application.housing_payment,
            requested_amount=application.requested_amount,
            settings=self.settings,
        )
        error_flags = [f for f in outcome.flags if f.get("severity") == "error"]
        if error_flags:
            raise ConflictError("Cannot submit application with validation errors")

        self.repo.add_validation(
            application_id=application.id,
            dti_ratio=outcome.dti_ratio,
            flags=outcome.flags,
            rules_version=outcome.rules_version,
            explanation=outcome.explanation,
        )
        application.status = ApplicationStatus.SUBMITTED.value
        self.repo.add_audit(
            application_id=application.id,
            actor_id=actor_id,
            action="APPLICATION_SUBMITTED",
            correlation_id=self._correlation(),
            detail={"status": application.status},
        )
        self.db.commit()
        self.db.refresh(application)
        return application

    def request_upload_url(
        self,
        application_id: uuid.UUID,
        payload: DocumentUploadRequest,
        actor_id: str,
    ) -> tuple[Document, str, int]:
        application = self.get(application_id)
        self.s3.validate_upload(payload.filename, payload.mime_type, payload.size_bytes)
        s3_key = self.s3.build_object_key(application.id, payload.filename)
        document = self.repo.create_document(
            application_id=application.id,
            s3_key=s3_key,
            mime_type=payload.mime_type,
            original_filename=payload.filename,
            size_bytes=payload.size_bytes,
            status=DocumentStatus.PENDING_UPLOAD,
        )
        upload_url = self.s3.create_presigned_put_url(s3_key, payload.mime_type)
        self.repo.add_audit(
            application_id=application.id,
            actor_id=actor_id,
            action="DOCUMENT_UPLOAD_URL_ISSUED",
            correlation_id=self._correlation(),
            detail={"document_id": str(document.id), "s3_key": s3_key},
        )
        self.db.commit()
        self.db.refresh(document)
        return document, upload_url, self.settings.presigned_url_expires_seconds

    def status_summary(self, application_id: uuid.UUID) -> dict[str, Any]:
        application = self.repo.get_with_relations(application_id)
        if not application:
            raise NotFoundError(f"Application {application_id} not found")

        outstanding: list[str] = []
        if application.status == ApplicationStatus.DRAFT.value:
            outstanding.append("Submit application")
        if not application.validation_results:
            outstanding.append("Run financial validation")
        pending_docs = [
            d
            for d in application.documents
            if d.status
            in {
                DocumentStatus.PENDING_UPLOAD.value,
                DocumentStatus.UPLOADED.value,
                DocumentStatus.PROCESSING.value,
            }
        ]
        if pending_docs:
            outstanding.append("Complete document processing")
        if application.status == ApplicationStatus.NEEDS_INFO.value:
            outstanding.append("Provide requested information")
        if application.status == ApplicationStatus.IN_REVIEW.value:
            outstanding.append("Await reviewer decision")

        latest = None
        if application.validation_results:
            latest = max(application.validation_results, key=lambda r: r.checked_at)

        return {
            "application": application,
            "outstanding_tasks": outstanding,
            "latest_validation": latest,
            "documents": application.documents,
        }

    def update_review_status(
        self,
        application_id: uuid.UUID,
        target: ApplicationStatus,
        actor_id: str,
        note: str | None = None,
    ) -> Application:
        application = self.get(application_id)
        assert_transition_allowed(application.status, target)
        application.status = target.value
        self.repo.add_audit(
            application_id=application.id,
            actor_id=actor_id,
            action="REVIEW_STATUS_UPDATED",
            correlation_id=self._correlation(),
            detail={"status": target.value, "note": note},
        )
        self.db.commit()
        self.db.refresh(application)
        return application
