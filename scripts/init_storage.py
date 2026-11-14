from botocore.exceptions import ClientError

from app.storage import bucket, s3

if __name__ == "__main__":
    try:
        s3().head_bucket(Bucket=bucket())
    except ClientError as exc:
        if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            raise
        s3().create_bucket(Bucket=bucket())
