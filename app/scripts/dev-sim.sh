#!/bin/bash
# dev-sim.sh — Rebuild the simulator build if native changed, install it, then start Metro.
# Builds directly against the hand-maintained ios/ project (no expo prebuild —
# that regeneration step and the app.config.js it read from are both gone as of
# the off-Expo migration's native ownership cutover). No dev-client either
# (expo-dev-client's native module was removed in that same cutover) — this
# boots straight into whatever Metro serves, no dev-launcher chooser screen.
# The Xcode project itself (Pear.xcodeproj/Pear.xcworkspace) is XcodeGen-generated
# from ios/project.yml, not committed — regenerate it unconditionally below so a
# stale checked-out project.pbxproj is never silently built against.
# pipefail matters here: xcodebuild is piped into xcbeautify below, so without it
# `set -e` only ever sees xcbeautify's exit code — a failed build reads as success,
# the stale .app from the previous build gets installed, and REV_FILE is written
# recording the failure as current (so the next run skips rebuilding entirely).
set -e
set -o pipefail

WORKSPACE="ios/Pear.xcworkspace"
SCHEME="Pear"
DERIVED_DATA="ios/build"
APP_PATH="$DERIVED_DATA/Build/Products/Debug-iphonesimulator/Pear.app"
REV_FILE=".dev-sim-rev"
BUNDLE_ID="com.plabrum.pear"

echo "Generating Xcode project..."
(cd ios && xcodegen generate)

# pod install has to follow every xcodegen run, not just the first. project.yml sets no
# configFiles, so the Pods xcconfigs are attached to the target purely by CocoaPods'
# own integration step — regenerating the project above drops that link, and the build
# then fails at `import React` with "no such module 'React'". CLAUDE.md documents the
# two as a pair for exactly this reason. Costs ~10s on a warm Podfile.lock.
echo "Installing pods..."
(cd ios && pod install)

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
# `HEAD:./ios`, not `HEAD:ios` — a `HEAD:path` rev is resolved from the repo root,
# where this directory is `app/ios`, so the bare form always died with exit 128 and
# contributed nothing (the tree hash of committed ios/ was silently missing from the
# rev). The `./` anchors it to the cwd instead. `|| true` keeps a genuine failure
# (detached tree, no HEAD) degrading to "hash the diff/status output only" rather
# than aborting the script now that pipefail makes the group's exit code count.
native_rev() {
  { git diff --stat -- ios/ package.json package-lock.json 2>/dev/null
    git status --porcelain -- ios/ package.json package-lock.json 2>/dev/null
    git rev-parse HEAD:./ios 2>/dev/null || true
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

  # ARCHS=arm64 is load-bearing. project.yml sets ONLY_ACTIVE_ARCH=YES for Debug, but
  # that only resolves against a -destination; with a bare -sdk there is no "active
  # arch", so xcodebuild falls back to every arch in ARCHS and tries an x86_64 slice.
  # Xcode 26 ships no x86_64 iOS-simulator Swift stdlib (it is Apple-Silicon-only, as
  # is every simulator runtime it installs), so that slice dies in SwiftEmitModule with
  # "missing required module 'SwiftShims'" while arm64 builds fine.
  BUILD_CMD=(xcodebuild
    -workspace "$WORKSPACE"
    -scheme "$SCHEME"
    -configuration Debug
    -sdk iphonesimulator
    -derivedDataPath "$DERIVED_DATA"
    ARCHS=arm64
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
echo "Launching Pear.app on simulator..."
xcrun simctl launch booted "$BUNDLE_ID" >/dev/null 2>&1 || true

echo "Starting Metro bundler..."
echo "(backend must be running separately — see 'just dev-backend' / 'just dev')"
npx react-native start
