#!/bin/bash
# dev-sim.sh — Rebuild dev client for simulator if native changed, then start Metro.
# Builds against ios/ (source of truth for Xcode Cloud, see
# .github/workflows/ios-drift-check.yml) — no EAS involved.
#
# PEAR_LOCAL_DEV=1 strips OTA code signing from app.config.js (see the comment
# there) and points updates.url at a local API, then incrementally re-prebuilds
# ios/ with that config — the same "expo prebuild -p ios" the drift-check CI job
# runs, just with dev values instead of prod ones. This intentionally leaves ios/
# locally modified; do NOT commit it like this. Before a real native-config change,
# restore it with:
#   EXPO_PUBLIC_API_URL=https://api.usepear.app npx expo prebuild -p ios --clean
set -e
export PEAR_LOCAL_DEV=1

WORKSPACE="ios/Pear.xcworkspace"
SCHEME="Pear"
DERIVED_DATA="ios/build"
APP_PATH="$DERIVED_DATA/Build/Products/Debug-iphonesimulator/Pear.app"
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

if [ ! -e "$APP_PATH" ]; then
  echo "No dev client build found."
  NEEDS_BUILD=true
elif [ ! -f "$FP_FILE" ] || [ "$(cat "$FP_FILE")" != "$CURRENT" ]; then
  echo "Native changes detected — rebuilding dev client..."
  NEEDS_BUILD=true
else
  echo "Dev client is up to date."
fi

if [ "$NEEDS_BUILD" = true ]; then
  echo "Re-prebuilding ios/ for local dev (signing stripped, local API URL)..."
  echo "  ios/ is now locally modified — do not commit it like this."
  npx expo prebuild -p ios

  echo "Building dev client for simulator (this takes a few minutes)..."

  BUILD_CMD=(xcodebuild
    -workspace "$WORKSPACE"
    -scheme "$SCHEME"
    -configuration Debug
    -sdk iphonesimulator
    -derivedDataPath "$DERIVED_DATA"
    build)

  if command -v xcbeautify >/dev/null 2>&1; then
    "${BUILD_CMD[@]}" | xcbeautify
  else
    "${BUILD_CMD[@]}"
  fi

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
echo "Starting Metro bundler..."
echo "(backend must be running separately — see 'just dev-backend' / 'just dev')"
npx expo start --dev-client --ios
