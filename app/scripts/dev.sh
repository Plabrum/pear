#!/bin/bash
# dev.sh — Start api edge function (background) and Metro (foreground) together.
set -e

echo "Starting api edge function (background)..."
npm run api:serve > /tmp/pear-api-serve.log 2>&1 &
API_SERVE_PID=$!
trap 'kill $API_SERVE_PID 2>/dev/null || true' EXIT INT TERM
echo "  api:serve PID $API_SERVE_PID — logs: /tmp/pear-api-serve.log"

echo ""
echo "Starting Metro bundler..."
npx expo start --dev-client
