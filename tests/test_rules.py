from decimal import Decimal as D

import pytest

from app.services import calculate_dti, evaluate_dti


@pytest.mark.parametrize(
    ("income", "debt", "housing", "expected"),
    [
        ("90000", "800", "1800", "34.67"),
        ("12000", "0", "430", "43.00"),
        ("12000", "0", "430.05", "43.01"),
        ("0.01", "9999999999.99", "9999999999.99", "2399999999997600.00"),
        ("12000", "0", "0", "0.00"),
    ],
)
def test_dti(income, debt, housing, expected):
    assert calculate_dti(D(income), D(debt), D(housing)) == D(expected)


@pytest.mark.parametrize(
    ("income", "debt", "housing"),
    [
        ("0", "1", "1"),
        ("1", "-1", "0"),
        ("1", "0", "-1"),
        ("NaN", "0", "0"),
    ],
)
def test_invalid_dti(income, debt, housing):
    with pytest.raises(ValueError):
        calculate_dti(D(income), D(debt), D(housing))


def test_threshold():
    assert evaluate_dti(D("43.00"), D("43.00")) == []
    assert evaluate_dti(D("43.01"), D("43.00"))[0]["code"] == "REVIEW_DTI"
