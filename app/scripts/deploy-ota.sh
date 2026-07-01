#!/bin/bash
set -e

ENV_FILE="${1:-.env.production}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: env file '$ENV_FILE' not found."
  exit 1
fi

# Temporarily hide .env.local so Expo doesn't load local values
if [ -f .env.local ]; then
  mv .env.local .env.local.bak
  trap "mv .env.local.bak .env.local" EXIT
fi

set -a
source "$ENV_FILE"
set +a

echo "Pushing OTA update..."
eas update --channel production --platform ios --message "${2:-ota update}"
