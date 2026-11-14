"""Shared domain enumerations."""

from enum import StrEnum


class ApplicationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    NEEDS_INFO = "NEEDS_INFO"
    COMPLETED = "COMPLETED"


class DocumentStatus(StrEnum):
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


# Allowed status transitions for PATCH/submit/review flows
ALLOWED_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.DRAFT: {ApplicationStatus.SUBMITTED},
    ApplicationStatus.SUBMITTED: {
        ApplicationStatus.IN_REVIEW,
        ApplicationStatus.NEEDS_INFO,
    },
    ApplicationStatus.IN_REVIEW: {
        ApplicationStatus.NEEDS_INFO,
        ApplicationStatus.COMPLETED,
    },
    ApplicationStatus.NEEDS_INFO: {
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.IN_REVIEW,
    },
    ApplicationStatus.COMPLETED: set(),
}
