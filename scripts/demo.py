"""Run the synthetic workflow against the local API and S3 emulator."""

import os
import subprocess
import sys
from pathlib import Path

import httpx


def main():
    sample = Path("examples/dummy.txt").read_bytes()
    applicant = {"Authorization": f"Bearer {os.environ['DEMO_APPLICANT_TOKEN']}"}
    reviewer = {"Authorization": f"Bearer {os.environ['DEMO_REVIEWER_TOKEN']}"}
    with httpx.Client(base_url=os.getenv("DEMO_BASE_URL", "http://127.0.0.1:8000")) as client:
        print("Ready:", client.get("/ready").raise_for_status().json())
        response = client.post(
            "/v1/applications",
            headers={**applicant, "Content-Type": "application/json"},
            content=Path("examples/application.json").read_bytes(),
        )
        application = response.raise_for_status().json()
        path = f"/v1/applications/{application['id']}"
        print("Create:", response.status_code, application["status"])
        result = client.post(f"{path}/validate", headers=applicant).raise_for_status().json()
        print("Validate:", result["dti_ratio"] + "% DTI", result["flags"])
        print(
            "Submit:",
            client.post(f"{path}/submit", headers=applicant).raise_for_status().json()["status"],
        )
        result = client.post(f"{path}/review", headers=reviewer, json={"status": "IN_REVIEW"})
        print("Review:", result.raise_for_status().json()["status"])
        response = client.post(
            f"{path}/documents/upload-url",
            headers=applicant,
            json={
                "filename": "dummy.txt",
                "mime_type": "text/plain",
                "size_bytes": len(sample),
            },
        )
        upload = response.raise_for_status().json()
        print(
            "Signed upload:",
            httpx.put(upload["url"], headers=upload["headers"], content=sample)
            .raise_for_status()
            .status_code,
        )
        if os.getenv("DEMO_REPLAY_IN_PROCESS") == "1":
            for _ in range(2):
                subprocess.run(
                    [sys.executable, "-m", "scripts.replay_upload", upload["document_id"]],
                    check=True,
                )
        else:
            for _ in range(2):
                subprocess.run(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "-T",
                        "api",
                        "python",
                        "-m",
                        "scripts.replay_upload",
                        upload["document_id"],
                    ],
                    check=True,
                )
        status = client.get(f"{path}/status", headers=applicant).raise_for_status().json()
        print("Document:", status["documents"][0]["status"])
        assert status["documents"][0]["status"] == "PROCESSED"
        audit = client.get(f"{path}/audit", headers=applicant).raise_for_status().json()
        count = sum(item["action"] == "DOCUMENT_PROCESSED" for item in audit)
        print("Processing audit events after duplicate delivery:", count)
        assert count == 1
        response = client.get(path)
        print("Unauthenticated request:", response.status_code)
        assert response.status_code == 401
        result = client.post(f"{path}/review", headers=reviewer, json={"status": "COMPLETED"})
        print("Complete:", result.raise_for_status().json()["status"])


if __name__ == "__main__":
    main()
