import os
from functools import cache

import boto3
from botocore.config import Config


@cache
def s3():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def bucket() -> str:
    return os.environ["DOCUMENT_BUCKET"]
