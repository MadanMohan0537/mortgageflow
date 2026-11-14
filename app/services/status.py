"""Application status transition rules."""

from app.core.errors import ConflictError
from app.models.enums import ALLOWED_TRANSITIONS, ApplicationStatus


def assert_transition_allowed(
    current: ApplicationStatus | str,
    target: ApplicationStatus | str,
) -> None:
    current_status = ApplicationStatus(current)
    target_status = ApplicationStatus(target)
    if current_status == target_status:
        return
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise ConflictError(
            f"Cannot transition from {current_status.value} to {target_status.value}"
        )


def can_edit_financial_fields(status: ApplicationStatus | str) -> bool:
    return ApplicationStatus(status) in {
        ApplicationStatus.DRAFT,
        ApplicationStatus.NEEDS_INFO,
    }
