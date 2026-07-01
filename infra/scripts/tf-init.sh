#!/usr/bin/env bash
# Initialise the Terraform S3 backend for Pear and select the production workspace.
#
# Mirrors the init logic in .github/workflows/_infrastructure.yml so local runs
# and CI agree on bucket/key/region. The state bucket name is derived, never
# hard-coded into the backend block (main.tf uses an empty `backend "s3" {}` and
# takes -backend-config flags here).
#
# Run from the infra/ directory (the root Justfile does `cd infra && ./scripts/tf-init.sh`).
#
# State bucket resolution order:
#   1. $STATE_BUCKET, if set explicitly.
#   2. tf-state-<aws-account-id>, if the AWS account id resolves.
#   3. tf-state-pear-<region>, as a stable fallback.
#
# Usage:
#   ./scripts/tf-init.sh
#   STATE_BUCKET=my-bucket ./scripts/tf-init.sh
#   AWS_REGION=us-west-2 ./scripts/tf-init.sh

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
STATE_KEY="pear/terraform.tfstate"
WORKSPACE="${WORKSPACE:-production}"

if ! command -v terraform >/dev/null 2>&1; then
  echo "error: terraform not found. Install with: brew install terraform" >&2
  exit 1
fi

# ── Derive the state bucket ───────────────────────────────────────────────────
if [[ -z "${STATE_BUCKET:-}" ]]; then
  ACCOUNT_ID=""
  if command -v aws >/dev/null 2>&1; then
    ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)"
  fi

  if [[ -n "$ACCOUNT_ID" && "$ACCOUNT_ID" != "None" ]]; then
    STATE_BUCKET="tf-state-${ACCOUNT_ID}"
  else
    echo "==> Could not resolve AWS account id; falling back to region-scoped bucket name" >&2
    STATE_BUCKET="tf-state-pear-${AWS_REGION}"
  fi
fi

echo "==> Backend config"
echo "    bucket:    ${STATE_BUCKET}"
echo "    key:       ${STATE_KEY}"
echo "    region:    ${AWS_REGION}"
echo "    encrypt:   true"
echo "    workspace: ${WORKSPACE}"

# ── Init the S3 backend ───────────────────────────────────────────────────────
terraform init -reconfigure \
  -backend-config="bucket=${STATE_BUCKET}" \
  -backend-config="key=${STATE_KEY}" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="encrypt=true"

# ── Select (or create) the workspace ──────────────────────────────────────────
terraform workspace select "${WORKSPACE}" 2>/dev/null \
  || terraform workspace new "${WORKSPACE}"

echo "==> Terraform initialised on workspace '${WORKSPACE}'"
