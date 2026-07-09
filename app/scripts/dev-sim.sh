#!/bin/bash
# dev-sim.sh — Rebuild the simulator build if native changed, install it, then start Metro.
# Builds directly against the hand-maintained ios/ project (no expo prebuild —
# that regeneration step and the app.config.js it read from are both gone as of
# the off-Expo migration's native ownership cutover). No dev-client either
# (expo-dev-client's native module was removed in that same cutover) — this
# boots straight into whatever Metro serves, no dev-launcher chooser screen.
set -e

WORKSPACE="ios/Pear.xcworkspace"
SCHEME="Pear"
DERIVED_DATA="ios/build"
APP_PATH="$DERIVED_DATA/Build/Products/Debug-iphonesimulator/Pear.app"
REV_FILE=".dev-sim-rev"

# Boots an available iPhone simulator if none is currently booted.
ensure_simulator_booted() {
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
    sleep 3
  fi
}

# Rebuild-avoidance: hash every native-affecting path's current working-tree
# content (tracked + uncommitted) and compare against what was last built.
# Replaces the old @expo/fingerprint-based cache (expo-updates, which computed
# that, is gone) — git already has a content hash for exactly this purpose.
native_rev() {
  { git diff --stat -- ios/ package.json package-lock.json 2>/dev/null
    git status --porcelain -- ios/ package.json package-lock.json 2>/dev/null
    git rev-parse HEAD:ios 2>/dev/null
  } | git hash-object --stdin
}

echo "Checking for native changes..."
CURRENT=$(native_rev)

NEEDS_BUILD=false

if [ ! -e "$APP_PATH" ]; then
  echo "No simulator build found."
  NEEDS_BUILD=true
elif [ ! -f "$REV_FILE" ] || [ "$(cat "$REV_FILE")" != "$CURRENT" ]; then
  echo "Native changes detected — rebuilding..."
  NEEDS_BUILD=true
else
  echo "Simulator build is up to date."
fi

if [ "$NEEDS_BUILD" = true ]; then
  echo "Building for simulator (this takes a few minutes)..."

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

  echo "Installing on booted simulator..."
  ensure_simulator_booted
  xcrun simctl install booted "$APP_PATH"
  echo "$CURRENT" > "$REV_FILE"
fi

# Ensure a simulator is booted before starting Metro
ensure_simulator_booted

echo ""
echo "Starting Metro bundler..."
echo "(backend must be running separately — see 'just dev-backend' / 'just dev')"
npx expo start --ios
