#!/usr/bin/env python3
"""Seed a few synthetic applications for local demos."""

from decimal import Decimal

from app.db.session import SessionLocal
from app.schemas.application import ApplicationCreate
from app.services.applications import ApplicationService

SAMPLES = [
    ApplicationCreate(
        applicant_alias="demo-user-001",
        annual_income=Decimal("90000.00"),
        monthly_debt=Decimal("800.00"),
        housing_payment=Decimal("1800.00"),
        requested_amount=Decimal("250000.00"),
    ),
    ApplicationCreate(
        applicant_alias="demo-user-002",
        annual_income=Decimal("55000.00"),
        monthly_debt=Decimal("1200.00"),
        housing_payment=Decimal("2100.00"),
        requested_amount=Decimal("320000.00"),
    ),
]


def main() -> None:
    with SessionLocal() as db:
        service = ApplicationService(db)
        for sample in SAMPLES:
            app = service.create(sample, actor_id="seed-script")
            print(f"Created {app.id} ({app.applicant_alias}) status={app.status}")


if __name__ == "__main__":
    main()
