"""Demonstration financial validation rules (not underwriting standards)."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import DomainValidationError


def calculate_dti(
    annual_income: Decimal,
    monthly_debt: Decimal,
    housing_payment: Decimal,
) -> Decimal:
    """Debt-to-income ratio as a percentage with two decimal places."""
    if annual_income <= 0 or monthly_debt < 0 or housing_payment < 0:
        raise ValueError("Invalid financial input")
    monthly_income = annual_income / Decimal("12")
    ratio = (monthly_debt + housing_payment) / monthly_income
    return (ratio * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class ValidationOutcome:
    dti_ratio: Decimal
    flags: list[dict[str, Any]]
    rules_version: str
    explanation: str


def evaluate_application(
    *,
    annual_income: Decimal | None,
    monthly_debt: Decimal | None,
    housing_payment: Decimal | None,
    requested_amount: Decimal | None,
    settings: Settings | None = None,
) -> ValidationOutcome:
    """Run demo-rule validation and return stored-result payload."""
    settings = settings or get_settings()
    flags: list[dict[str, Any]] = []

    required = {
        "annual_income": annual_income,
        "monthly_debt": monthly_debt,
        "housing_payment": housing_payment,
        "requested_amount": requested_amount,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        for name in missing:
            flags.append(
                {
                    "code": "MISSING_REQUIRED_FIELD",
                    "message": f"Missing required field: {name}",
                    "severity": "error",
                    "field": name,
                }
            )
        return ValidationOutcome(
            dti_ratio=Decimal("0.00"),
            flags=flags,
            rules_version=settings.rules_version,
            explanation="Required fields are missing; DTI was not calculated.",
        )

    assert annual_income is not None
    assert monthly_debt is not None
    assert housing_payment is not None
    assert requested_amount is not None

    if annual_income <= 0:
        raise DomainValidationError(
            "annual_income must be greater than zero",
            details=[{"field": "annual_income", "message": "must be > 0"}],
        )
    if monthly_debt < 0 or housing_payment < 0 or requested_amount <= 0:
        raise DomainValidationError(
            "Financial amounts must be non-negative and requested_amount > 0",
            details=[{"message": "invalid financial amounts"}],
        )

    dti = calculate_dti(annual_income, monthly_debt, housing_payment)
    threshold = Decimal(settings.dti_review_threshold)

    if dti > threshold:
        flags.append(
            {
                "code": "REVIEW_DTI",
                "message": (
                    f"DTI {dti}% exceeds demonstration threshold {threshold}%. "
                    "This is an example review flag, not a lending denial."
                ),
                "severity": "review",
            }
        )
    else:
        flags.append(
            {
                "code": "DTI_WITHIN_THRESHOLD",
                "message": (
                    f"DTI {dti}% is within demonstration threshold {threshold}%."
                ),
                "severity": "info",
            }
        )

    if requested_amount > annual_income * Decimal("5"):
        flags.append(
            {
                "code": "HIGH_LOAN_TO_INCOME",
                "message": (
                    "Requested amount exceeds 5x annual income "
                    "(demonstration heuristic only)."
                ),
                "severity": "review",
            }
        )

    explanation = (
        f"Calculated DTI={dti}% using rules_version={settings.rules_version}. "
        "Flags are educational demo outcomes, not credit decisions."
    )
    return ValidationOutcome(
        dti_ratio=dti,
        flags=flags,
        rules_version=settings.rules_version,
        explanation=explanation,
    )
