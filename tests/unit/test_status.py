"""Unit tests for status transition rules."""

import pytest

from app.core.errors import ConflictError
from app.models.enums import ApplicationStatus
from app.services.status import assert_transition_allowed, can_edit_financial_fields


def test_draft_to_submitted_allowed():
    assert_transition_allowed(ApplicationStatus.DRAFT, ApplicationStatus.SUBMITTED)


def test_completed_to_draft_rejected():
    with pytest.raises(ConflictError):
        assert_transition_allowed(
            ApplicationStatus.COMPLETED, ApplicationStatus.DRAFT
        )


def test_financial_edits_only_in_editable_states():
    assert can_edit_financial_fields(ApplicationStatus.DRAFT) is True
    assert can_edit_financial_fields(ApplicationStatus.NEEDS_INFO) is True
    assert can_edit_financial_fields(ApplicationStatus.SUBMITTED) is False
    assert can_edit_financial_fields(ApplicationStatus.COMPLETED) is False
