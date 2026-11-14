"""Create synthetic drafts through the authenticated API for local demos and benchmarks."""

import argparse
import os
from decimal import Decimal

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")

    token = os.environ.get("DEMO_APPLICANT_TOKEN")
    if not token:
        parser.error("Set DEMO_APPLICANT_TOKEN to a demo applicant bearer token")

    with httpx.Client(base_url=args.base, headers={"Authorization": f"Bearer {token}"}) as client:
        for number in range(1, args.count + 1):
            monthly_debt = Decimal("800.00") if number % 2 else Decimal("2000.00")
            result = client.post(
                "/v1/applications",
                json={
                    "applicant_alias": f"seed-demo-{number:04d}",
                    "annual_income": "90000.00",
                    "monthly_debt": str(monthly_debt),
                    "housing_payment": "1800.00",
                    "requested_amount": "250000.00",
                },
            )
            if result.status_code != 201:
                raise SystemExit(f"Created {number - 1} drafts before HTTP {result.status_code}")
    print(f"Created {args.count} synthetic drafts")


if __name__ == "__main__":
    main()
