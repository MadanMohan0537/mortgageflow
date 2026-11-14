"""Simple Locust load script for local latency baselines.

Usage (API running locally):
  locust -f scripts/locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 30s
"""

from locust import HttpUser, between, task

API_KEY = "dev-api-key-change-me"
HEADERS = {"X-API-Key": API_KEY, "X-Actor-Id": "load-tester"}


class MortgageFlowUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(3)
    def health(self) -> None:
        self.client.get("/health")

    @task(2)
    def list_applications(self) -> None:
        self.client.get("/v1/applications?page=1&page_size=10", headers=HEADERS)

    @task(1)
    def create_application(self) -> None:
        self.client.post(
            "/v1/applications",
            headers=HEADERS,
            json={
                "applicant_alias": "load-user",
                "annual_income": "90000.00",
                "monthly_debt": "800.00",
                "housing_payment": "1800.00",
                "requested_amount": "250000.00",
            },
        )
