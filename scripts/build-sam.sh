#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cd "$root"
cp -r app workers migrations requirements.txt alembic.ini template.yaml "$stage/"
find "$stage" -type d -name __pycache__ -prune -exec rm -rf {} +
curl --fail --silent --show-error --location \
  https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
  -o "$stage/global-bundle.pem"
sam validate --template-file "$stage/template.yaml"
sam build --template-file "$stage/template.yaml" --build-dir "$root/.aws-sam/build" "$@"
