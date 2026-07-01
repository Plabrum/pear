#!/bin/zsh
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> Stopping local Supabase..."
supabase stop

echo "==> Stopping Colima..."
colima stop

echo "Done."
