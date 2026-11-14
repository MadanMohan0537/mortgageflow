"""Unit tests for DTI calculation and demo-rule engine."""

from decimal import Decimal

import pytest

from app.core.config import Settings
from app.core.errors import DomainValidationError
from app.services.validation import calculate_dti, evaluate_application


def test_calculate_dti_example_from_guide():
    result = calculate_dti(
        Decimal("90000.00"),
        Decimal("800.00"),
        Decimal("1800.00"),
    )
    assert result == Decimal("34.67")


def test_calculate_dti_rejects_zero_income():
    with pytest.raises(ValueError):
        calculate_dti(Decimal("0"), Decimal("100"), Decimal("100"))


def test_calculate_dti_rejects_negative_debt():
    with pytest.raises(ValueError):
        calculate_dti(Decimal("90000"), Decimal("-1"), Decimal("100"))


def test_evaluate_flags_review_dti_above_threshold():
    settings = Settings(dti_review_threshold=Decimal("30.00"), rules_version="demo-v-test")
    outcome = evaluate_application(
        annual_income=Decimal("90000.00"),
        monthly_debt=Decimal("800.00"),
        housing_payment=Decimal("1800.00"),
        requested_amount=Decimal("250000.00"),
        settings=settings,
    )
    codes = {flag["code"] for flag in outcome.flags}
    assert "REVIEW_DTI" in codes
    assert outcome.dti_ratio == Decimal("34.67")
    assert outcome.rules_version == "demo-v-test"


def test_evaluate_within_threshold():
    settings = Settings(dti_review_threshold=Decimal("43.00"))
    outcome = evaluate_application(
        annual_income=Decimal("90000.00"),
        monthly_debt=Decimal("800.00"),
        housing_payment=Decimal("1800.00"),
        requested_amount=Decimal("250000.00"),
        settings=settings,
    )
    codes = {flag["code"] for flag in outcome.flags}
    assert "DTI_WITHIN_THRESHOLD" in codes
    assert "REVIEW_DTI" not in codes


def test_evaluate_missing_fields():
    outcome = evaluate_application(
        annual_income=None,
        monthly_debt=Decimal("100"),
        housing_payment=Decimal("100"),
        requested_amount=Decimal("100"),
    )
    assert any(f["code"] == "MISSING_REQUIRED_FIELD" for f in outcome.flags)


def test_evaluate_domain_error_on_zero_income():
    with pytest.raises(DomainValidationError):
        evaluate_application(
            annual_income=Decimal("0"),
            monthly_debt=Decimal("100"),
            housing_payment=Decimal("100"),
            requested_amount=Decimal("100"),
        )


def test_boundary_exact_threshold_not_review():
    # DTI exactly at threshold should not raise REVIEW_DTI (> threshold only)
    settings = Settings(dti_review_threshold=Decimal("34.67"))
    outcome = evaluate_application(
        annual_income=Decimal("90000.00"),
        monthly_debt=Decimal("800.00"),
        housing_payment=Decimal("1800.00"),
        requested_amount=Decimal("100000.00"),
        settings=settings,
    )
    codes = {flag["code"] for flag in outcome.flags}
    assert "REVIEW_DTI" not in codes
