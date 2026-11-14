from decimal import ROUND_HALF_UP, Decimal

from app.schemas import Status

REVIEW_TRANSITIONS = {
    Status.SUBMITTED: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.NEEDS_INFO, Status.COMPLETED},
    Status.NEEDS_INFO: {Status.IN_REVIEW},
}


def calculate_dti(income: Decimal, debt: Decimal, housing: Decimal) -> Decimal:
    if not all(value.is_finite() for value in (income, debt, housing)):
        raise ValueError("Use finite financial values")
    if income <= 0 or min(debt, housing) < 0:
        raise ValueError("Invalid financial input")
    return ((debt + housing) * 1200 / income).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def evaluate_dti(dti: Decimal, threshold: Decimal) -> list[dict[str, str]]:
    if dti > threshold:
        return [
            {"code": "REVIEW_DTI", "message": f"DTI exceeds the {threshold}% example threshold."}
        ]
    return []
