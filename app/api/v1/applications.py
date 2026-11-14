"""Application API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_actor_id, require_api_key
from app.db.session import get_db
from app.models.enums import ApplicationStatus
from app.schemas.application import (
    ApplicationCreate,
    ApplicationCreated,
    ApplicationRead,
    ApplicationStatusResponse,
    ApplicationUpdate,
    DocumentRead,
    DocumentUploadRequest,
    DocumentUploadUrlResponse,
    ReviewStatusUpdate,
    ValidationResultRead,
)
from app.schemas.common import PaginatedResponse
from app.services.applications import ApplicationService

router = APIRouter(prefix="/applications", tags=["applications"])


def get_service(db: Session = Depends(get_db)) -> ApplicationService:
    return ApplicationService(db)


@router.post(
    "",
    response_model=ApplicationCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_application(
    payload: ApplicationCreate,
    service: Annotated[ApplicationService, Depends(get_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ApplicationCreated:
    application = service.create(payload, actor_id)
    return ApplicationCreated.model_validate(application)


@router.get(
    "",
    response_model=PaginatedResponse[ApplicationRead],
    dependencies=[Depends(require_api_key)],
)
def list_applications(
    service: Annotated[ApplicationService, Depends(get_service)],
    status_filter: Annotated[
        ApplicationStatus | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[ApplicationRead]:
    items, total = service.list(
        status=status_filter, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=[ApplicationRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationRead,
    dependencies=[Depends(require_api_key)],
)
def get_application(
    application_id: UUID,
    service: Annotated[ApplicationService, Depends(get_service)],
) -> ApplicationRead:
    return ApplicationRead.model_validate(service.get(application_id))


@router.patch(
    "/{application_id}",
    response_model=ApplicationRead,
    dependencies=[Depends(require_api_key)],
)
def update_application(
    application_id: UUID,
    payload: ApplicationUpdate,
    service: Annotated[ApplicationService, Depends(get_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ApplicationRead:
    return ApplicationRead.model_validate(
        service.update(application_id, payload, actor_id)
    )


@router.post(
    "/{application_id}/validate",
    response_model=ValidationResultRead,
    dependencies=[Depends(require_api_key)],
)
def validate_application(
    application_id: UUID,
    service: Annotated[ApplicationService, Depends(get_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ValidationResultRead:
    return ValidationResultRead.model_validate(
        service.validate(application_id, actor_id)
    )


@router.post(
    "/{application_id}/submit",
    response_model=ApplicationRead,
    dependencies=[Depends(require_api_key)],
)
def submit_application(
    application_id: UUID,
    service: Annotated[ApplicationService, Depends(get_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ApplicationRead:
    return ApplicationRead.model_validate(service.submit(application_id, actor_id))


@router.post(
    "/{application_id}/documents/upload-url",
    response_model=DocumentUploadUrlResponse,
    dependencies=[Depends(require_api_key)],
)
def create_document_upload_url(
    application_id: UUID,
    payload: DocumentUploadRequest,
    service: Annotated[ApplicationService, Depends(get_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> DocumentUploadUrlResponse:
    document, upload_url, expires = service.request_upload_url(
        application_id, payload, actor_id
    )
    return DocumentUploadUrlResponse(
        document_id=document.id,
        upload_url=upload_url,
        s3_key=document.s3_key,
        expires_in_seconds=expires,
        status=document.status,
    )


@router.get(
    "/{application_id}/status",
    response_model=ApplicationStatusResponse,
    dependencies=[Depends(require_api_key)],
)
def get_application_status(
    application_id: UUID,
    service: Annotated[ApplicationService, Depends(get_service)],
) -> ApplicationStatusResponse:
    summary = service.status_summary(application_id)
    latest = summary["latest_validation"]
    return ApplicationStatusResponse(
        id=summary["application"].id,
        status=summary["application"].status,
        outstanding_tasks=summary["outstanding_tasks"],
        latest_validation=(
            ValidationResultRead.model_validate(latest) if latest else None
        ),
        documents=[DocumentRead.model_validate(d) for d in summary["documents"]],
    )


@router.post(
    "/{application_id}/review",
    response_model=ApplicationRead,
    dependencies=[Depends(require_api_key)],
)
def update_review_status(
    application_id: UUID,
    payload: ReviewStatusUpdate,
    service: Annotated[ApplicationService, Depends(get_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ApplicationRead:
    return ApplicationRead.model_validate(
        service.update_review_status(
            application_id, payload.status, actor_id, payload.note
        )
    )
