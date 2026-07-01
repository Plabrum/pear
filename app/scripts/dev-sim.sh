#!/bin/bash
# dev-sim.sh — Rebuild dev client for simulator if native changed, then start Metro
set -e

SIM_BUILD="builds/dev-sim.app"
FP_FILE=".dev-sim-fingerprint"

get_fingerprint() {
  npx expo-updates fingerprint:generate --platform ios 2>/dev/null \
    | node -e "let s=''; process.stdin.on('data',d=>s+=d); process.stdin.on('end',()=>console.log(JSON.parse(s).hash))"
}

echo "Checking for native changes..."
CURRENT=$(get_fingerprint)

if [ -z "$CURRENT" ]; then
  echo "Error: Could not generate fingerprint. Is expo-updates installed?"
  exit 1
fi

NEEDS_BUILD=false

if [ ! -e "$SIM_BUILD" ]; then
  echo "No dev client build found."
  NEEDS_BUILD=true
elif [ ! -f "$FP_FILE" ] || [ "$(cat "$FP_FILE")" != "$CURRENT" ]; then
  echo "Native changes detected — rebuilding dev client..."
  NEEDS_BUILD=true
else
  echo "Dev client is up to date."
fi

if [ "$NEEDS_BUILD" = true ]; then
  echo "Building dev client for simulator (this takes a few minutes)..."
  EAS_BUILD_NO_EXPO_GO_WARNING=true eas build \
    --platform ios \
    --profile development-simulator \
    --local \
    --output "$SIM_BUILD"

  bash scripts/install-dev-sim.sh
fi

# Ensure a simulator is booted before starting Metro
BOOTED=$(xcrun simctl list devices booted 2>/dev/null | grep -c "(Booted)" || true)
if [ "$BOOTED" -eq 0 ]; then
  UDID=$(xcrun simctl list devices available -j \
    | node -e "let s=''; process.stdin.on('data',d=>s+=d); process.stdin.on('end',()=>{
        const devs=JSON.parse(s).devices;
        const iphone=Object.values(devs).flat().find(x=>x.name.includes('iPhone')&&x.isAvailable);
        console.log(iphone?iphone.udid:'');
      })")
  if [ -z "$UDID" ]; then
    echo "Error: no available iPhone simulator found."
    exit 1
  fi
  echo "Booting simulator $UDID..."
  xcrun simctl boot "$UDID"
  open -a Simulator
fi

echo ""
echo "Starting api edge function (background)..."
npm run api:serve > /tmp/pear-api-serve.log 2>&1 &
API_SERVE_PID=$!
trap 'kill $API_SERVE_PID 2>/dev/null || true' EXIT INT TERM
echo "  api:serve PID $API_SERVE_PID — logs: /tmp/pear-api-serve.log"

echo ""
echo "Starting Metro bundler..."
npx expo start --dev-client --ios
