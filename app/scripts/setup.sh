#!/bin/zsh
set -e

echo "==> Installing Homebrew..."
if ! command -v brew &>/dev/null; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add Homebrew to PATH for Apple Silicon
  if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
  fi
else
  echo "   Homebrew already installed, skipping."
fi

echo "==> Installing Node.js (includes npm)..."
if ! command -v node &>/dev/null; then
  brew install node
else
  echo "   Node already installed: $(node -v)"
fi

echo "==> Installing Colima (Docker runtime)..."
if ! command -v colima &>/dev/null; then
  brew install colima docker
  colima start
else
  echo "   Colima already installed, skipping."
  if ! colima status 2>/dev/null | grep -q "running"; then
    colima start
  fi
fi

echo "==> Installing PostgreSQL client (psql)..."
if ! command -v psql &>/dev/null; then
  brew install libpq
  brew link --force libpq
else
  echo "   psql already installed, skipping."
fi

echo "==> Installing Supabase CLI..."
if ! command -v supabase &>/dev/null; then
  brew install supabase/tap/supabase
else
  echo "   Supabase CLI already installed, skipping."
fi

echo "==> Installing project dependencies..."
cd "$(dirname "$0")/.."
npm install

echo ""
echo "Setup complete! Run the app with:"
echo "  npm run web"
