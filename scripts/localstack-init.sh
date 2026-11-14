#!/bin/sh
set -euo pipefail
awslocal s3 mb s3://mortgageflow-docs-local || true
awslocal s3api put-bucket-encryption \
  --bucket mortgageflow-docs-local \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' || true
echo "LocalStack S3 bucket ready"
