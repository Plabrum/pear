#!/bin/zsh
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/app"
cd "$ROOT"

echo "==> Resetting database (applying all migrations)..."
supabase db reset

echo "==> Generating types..."
(cd "$APP" && npm run db:types)

echo "Database reset complete."
