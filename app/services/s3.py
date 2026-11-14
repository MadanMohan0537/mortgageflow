"""S3 helpers for pre-signed uploads (LocalStack-compatible)."""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

import boto3
from botocore.client import Config

from app.core.config import Settings, get_settings
from app.core.errors import DomainValidationError


class S3Service:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        client_kwargs: dict = {
            "service_name": "s3",
            "region_name": self.settings.aws_region,
            "aws_access_key_id": self.settings.aws_access_key_id,
            "aws_secret_access_key": self.settings.aws_secret_access_key,
            "config": Config(signature_version="s3v4"),
        }
        if self.settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = self.settings.s3_endpoint_url
        self.client = boto3.client(**client_kwargs)

    def validate_upload(
        self, filename: str, mime_type: str, size_bytes: int
    ) -> str:
        extension = PurePosixPath(filename).suffix.lower()
        if extension not in self.settings.allowed_extensions:
            raise DomainValidationError(
                "Unsupported file type",
                details=[
                    {
                        "field": "filename",
                        "message": (
                            f"Allowed extensions: "
                            f"{sorted(self.settings.allowed_extensions)}"
                        ),
                    }
                ],
            )
        if size_bytes <= 0 or size_bytes > self.settings.max_document_bytes:
            raise DomainValidationError(
                "Invalid file size",
                details=[
                    {
                        "field": "size_bytes",
                        "message": (
                            f"Must be between 1 and "
                            f"{self.settings.max_document_bytes} bytes"
                        ),
                    }
                ],
            )
        if not mime_type:
            raise DomainValidationError(
                "mime_type is required",
                details=[{"field": "mime_type", "message": "required"}],
            )
        return extension

    def build_object_key(self, application_id: uuid.UUID, filename: str) -> str:
        safe_name = PurePosixPath(filename).name.replace(" ", "_")
        return f"applications/{application_id}/{uuid.uuid4()}_{safe_name}"

    def create_presigned_put_url(self, s3_key: str, mime_type: str) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.settings.s3_bucket,
                "Key": s3_key,
                "ContentType": mime_type,
            },
            ExpiresIn=self.settings.presigned_url_expires_seconds,
        )
