#!/usr/bin/env bash
# Open an SSM Session Manager shell on the Pear prod EC2 host.
#
# No SSH keys, no open ports — uses AWS SSM. Requires:
#   - AWS creds with ssm:StartSession on the instance
#   - session-manager-plugin (brew install --cask session-manager-plugin)
#
# Usage:
#   scripts/prod-ssh.sh                 # interactive shell as ssm-user
#   scripts/prod-ssh.sh -- whoami       # run one command and exit
#   INSTANCE_ID=i-abc scripts/prod-ssh.sh
#   AWS_REGION=us-west-2 scripts/prod-ssh.sh

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"

if ! command -v aws >/dev/null 2>&1; then
  echo "error: aws CLI not found. Install with: brew install awscli" >&2
  exit 1
fi

if ! command -v session-manager-plugin >/dev/null 2>&1; then
  echo "error: session-manager-plugin not found." >&2
  echo "  brew install --cask session-manager-plugin" >&2
  exit 1
fi

# Prefer the terraform output; the root Justfile invokes this from the repo root,
# so reach into infra/ for state.
if [[ -z "${INSTANCE_ID:-}" ]]; then
  if [[ -d infra ]]; then
    INSTANCE_ID="$(cd infra && terraform output -raw instance_id 2>/dev/null || true)"
  fi
fi

if [[ -z "${INSTANCE_ID:-}" ]]; then
  echo "==> Resolving instance via tag Name=pear*"
  INSTANCE_ID="$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters "Name=tag:Name,Values=pear*" "Name=instance-state-name,Values=running" \
    --query 'Reservations[].Instances[].InstanceId | [0]' \
    --output text)"
fi

if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
  echo "error: could not resolve prod instance id. Set INSTANCE_ID=i-..." >&2
  exit 1
fi

echo "==> Connecting to $INSTANCE_ID in $AWS_REGION"

# Drop the literal "--" separator just-style invocations leave behind so users
# can do `just prod-ssh -- whoami`.
if [[ "${1:-}" == "--" ]]; then
  shift
fi

if [[ $# -gt 0 ]]; then
  CMD="$*"
  exec aws ssm start-session \
    --region "$AWS_REGION" \
    --target "$INSTANCE_ID" \
    --document-name AWS-StartInteractiveCommand \
    --parameters "command=[\"sudo -i bash -lc '$CMD'\"]"
else
  exec aws ssm start-session \
    --region "$AWS_REGION" \
    --target "$INSTANCE_ID"
fi
