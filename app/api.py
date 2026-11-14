from pathlib import PurePath
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import engine, threshold
from app.models import Application, AuditEvent, Document, Validation
from app.repository import application_scope, audit, find_application
from app.schemas import (
    DOCUMENT_TYPES,
    ApplicationInput,
    ApplicationPatch,
    ApplicationView,
    AuditView,
    Page,
    ReviewInput,
    Status,
    StatusView,
    UploadInput,
    UploadView,
    ValidationView,
)
from app.security import Actor, authenticate
from app.services import REVIEW_TRANSITIONS, calculate_dti, evaluate_dti
from app.storage import bucket, s3

router = APIRouter(prefix="/v1/applications", tags=["applications"])


def database():
    with Session(engine(), expire_on_commit=False) as session:
        yield session


DB = Annotated[Session, Depends(database)]
User = Annotated[Actor, Depends(authenticate)]


def load(db: Session, app_id: UUID, actor: Actor, *, lock: bool = False) -> Application:
    application = find_application(db, app_id, actor.id, actor.role, lock=lock)
    if application is None:
        raise HTTPException(404, "Application not found")
    return application


def record(db: Session, request: Request, application: Application, actor: Actor, action: str):
    audit(db, application.id, actor.id, action, request.state.correlation_id)
    db.commit()


@router.post("", status_code=201, response_model=ApplicationView)
def create_application(body: ApplicationInput, request: Request, actor: User, db: DB):
    actor.require("applicant")
    application = Application(owner_id=actor.id, **body.model_dump())
    db.add(application)
    db.flush()
    record(db, request, application, actor, "APPLICATION_CREATED")
    return application


@router.get("", response_model=Page)
def list_applications(
    actor: User,
    db: DB,
    status: Status | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
):
    query = application_scope(actor.id, actor.role)
    if status:
        query = query.where(Application.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(Application.created_at.desc(), Application.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {"items": items, "limit": limit, "offset": offset, "total": total}


@router.get("/{app_id}", response_model=ApplicationView)
def read_application(app_id: UUID, actor: User, db: DB):
    return load(db, app_id, actor)


@router.patch("/{app_id}", response_model=ApplicationView)
def update_application(app_id: UUID, body: ApplicationPatch, request: Request, actor: User, db: DB):
    actor.require("applicant")
    application = load(db, app_id, actor, lock=True)
    if application.status not in {Status.DRAFT, Status.NEEDS_INFO}:
        raise HTTPException(
            409, "Only draft applications and applications needing info can be edited"
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    record(db, request, application, actor, "APPLICATION_UPDATED")
    return application


@router.post("/{app_id}/validate", response_model=ValidationView)
def validate_application(app_id: UUID, request: Request, actor: User, db: DB):
    application = load(db, app_id, actor, lock=True)
    dti = calculate_dti(
        application.annual_income, application.monthly_debt, application.housing_payment
    )
    result = Validation(
        application_id=app_id,
        dti_ratio=dti,
        flags=evaluate_dti(dti, threshold()),
        rules_version="demo-1",
        threshold=threshold(),
    )
    db.add(result)
    record(db, request, application, actor, "VALIDATION_RECORDED")
    return result


@router.post("/{app_id}/submit", response_model=ApplicationView)
def submit_application(app_id: UUID, request: Request, actor: User, db: DB):
    actor.require("applicant")
    application = load(db, app_id, actor, lock=True)
    if application.status == Status.DRAFT:
        application.status = Status.SUBMITTED
    elif application.status == Status.NEEDS_INFO:
        application.status = Status.IN_REVIEW
    else:
        raise HTTPException(409, "Application cannot be submitted from its current status")
    record(db, request, application, actor, f"STATUS_{application.status}")
    return application


@router.post("/{app_id}/review", response_model=ApplicationView)
def review_application(app_id: UUID, body: ReviewInput, request: Request, actor: User, db: DB):
    actor.require("reviewer")
    application = load(db, app_id, actor, lock=True)
    if body.status not in REVIEW_TRANSITIONS.get(Status(application.status), set()):
        raise HTTPException(409, "Invalid review transition")
    application.status = body.status
    record(db, request, application, actor, f"STATUS_{application.status}")
    return application


@router.post("/{app_id}/documents/upload-url", response_model=UploadView, status_code=201)
def upload_url(app_id: UUID, body: UploadInput, request: Request, actor: User, db: DB):
    actor.require("applicant")
    application = load(db, app_id, actor, lock=True)
    if application.status == Status.COMPLETED:
        raise HTTPException(409, "Completed applications cannot accept documents")
    suffix = PurePath(body.filename).suffix.lower()
    if DOCUMENT_TYPES.get(suffix) != body.mime_type:
        raise HTTPException(400, "File extension must match the supplied PDF or text content type")
    doc_id = uuid4()
    key = f"applications/{app_id}/{doc_id}{suffix}"
    url = s3().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket(),
            "Key": key,
            "ContentType": body.mime_type,
            "ContentLength": body.size_bytes,
            "IfNoneMatch": "*",
        },
        ExpiresIn=300,
    )
    db.add(
        Document(
            id=doc_id,
            application_id=app_id,
            mime_type=body.mime_type,
            s3_key=key,
            expected_size=body.size_bytes,
        )
    )
    record(db, request, application, actor, "DOCUMENT_UPLOAD_REQUESTED")
    return {
        "document_id": doc_id,
        "url": url,
        "expires_in": 300,
        "headers": {
            "Content-Type": body.mime_type,
            "Content-Length": str(body.size_bytes),
            "If-None-Match": "*",
        },
    }


@router.get("/{app_id}/status", response_model=StatusView)
def application_status(app_id: UUID, actor: User, db: DB):
    application = load(db, app_id, actor)
    documents = db.scalars(
        select(Document)
        .where(Document.application_id == app_id)
        .order_by(Document.created_at, Document.id)
    ).all()
    tasks = {
        Status.DRAFT: ["Submit application"],
        Status.SUBMITTED: ["Await review"],
        Status.IN_REVIEW: ["Await review outcome"],
        Status.NEEDS_INFO: ["Update requested information and resubmit"],
    }.get(Status(application.status), [])
    if any(doc.status == "PENDING" for doc in documents):
        tasks.append("Check pending document uploads")
    if (
        any(doc.status == "REJECTED" for doc in documents)
        and application.status != Status.COMPLETED
    ):
        tasks.append("Replace rejected documents")
    return {"status": application.status, "outstanding_tasks": tasks, "documents": documents}


@router.get("/{app_id}/audit", response_model=list[AuditView])
def application_audit(
    app_id: UUID,
    actor: User,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    load(db, app_id, actor)
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.application_id == app_id)
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
            .offset(offset)
            .limit(limit)
        )
    )
