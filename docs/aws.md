# AWS demo deployment

Use a development AWS account with a budget alert. The stack creates a private RDS instance, a private S3 bucket, Lambda functions, an API Gateway HTTP API, CloudWatch logs and alarms, and a failure queue. RDS storage, CloudWatch, VPC endpoints and NAT can incur costs while idle. Check the AWS Pricing Calculator in the target region. Local Docker Compose is the lowest-cost supported setup.

## Prerequisites

- AWS CLI and AWS SAM CLI, authenticated in the intended development account and region.
- Docker for the container-based SAM build.
- One VPC and at least two private subnets in different availability zones with DNS and network paths to S3 and Secrets Manager. Use a NAT path or S3 gateway and Secrets Manager interface endpoints with private DNS. Allow HTTPS from the Lambda security group on the Secrets Manager endpoint when using an interface endpoint.
- A Secrets Manager secret containing the API identity map. Use unique tokens generated with `secrets.token_urlsafe(32)` and the roles `applicant` and `reviewer`. Supply the secret ARN, never the literal secret. Use the default Secrets Manager KMS key or grant the functions appropriate decrypt access for a customer-managed key.
- A globally unique S3 bucket name. Use the same region for the stack, VPC and secret.

## Build and deploy

```sh
./scripts/build-sam.sh --use-container
sam deploy --guided --template-file .aws-sam/build/template.yaml
```

Supply `VpcId`, comma-separated `PrivateSubnets`, `DocumentBucketName`, and `IdentitySecretArn`. SAM requires permission to create IAM roles. The gateway exposes health probes and forwards application requests to FastAPI for bearer-token authentication.

Run the database migration using the stack's `MigrationFunctionName` output. Run it again after each deployment that adds a migration.

```sh
aws lambda invoke --function-name "$MIGRATION_FUNCTION" --cli-read-timeout 130 migration-result.json
jq -e '.status == "migrated"' migration-result.json
curl -fsS "$API_URL/ready"
```

Use the README curl flow with the AWS URL and the tokens from the identity secret. For the document example, omit the local replay command and poll the status endpoint until the document is `PROCESSED`. Keep the S3 object key and correlation ID for troubleshooting. The worker uses the object key, an event fingerprint, and a database lock to make duplicate delivery safe.

This demo uses the RDS-managed master secret for migrations and runtime database access. An expanded deployment can split credentials into migration and runtime database roles. Rotate identity tokens by updating the AWS secret and replacing warm function environments. The implementation caches secrets per execution environment.

## Monitoring and recovery

Use the dashboard for HTTP counts, latency, 4xx/5xx, worker timing and failure metrics. Subscribe an operator to the stack's SNS topic to receive alarms. Inspect the API and worker log groups by correlation ID. Use Logs Insights to count database failures or rejected uploads.

```text
fields @timestamp, @message
| filter @message like /database_failure|document_processing_failure|REJECTED/
| sort @timestamp desc
| limit 50
```

Transient failures cause Lambda to retry. When a notification lands in the failure queue, inspect the logs and fix the cause before replaying the queue message body as the worker event. Delete the queue message only after successful replay. For a rejected upload, ask the synthetic applicant to request a new upload URL.

## Tear down

1. Empty the synthetic document bucket with `aws s3 rm "s3://$DOCUMENT_BUCKET" --recursive`.
2. Delete the demo stack with `sam delete --stack-name "$STACK_NAME"`. The stack deletes its RDS database, including the synthetic records.
3. Remove the identity secret and any separately created VPC endpoints, NAT, subscriptions, or packaging artifacts dedicated to this demo. Check the development account for remaining billable resources.
