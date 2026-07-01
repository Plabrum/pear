#!/bin/bash
# install-dev-sim.sh — Extract, install, and fingerprint the dev-sim build.
# Called by dev-sim.sh after a build, and by build:dev-sim via package.json.
set -e

SIM_BUILD="builds/dev-sim.app"
FP_FILE=".dev-sim-fingerprint"

get_fingerprint() {
  npx expo-updates fingerprint:generate --platform ios 2>/dev/null \
    | node -e "let s=''; process.stdin.on('data',d=>s+=d); process.stdin.on('end',()=>console.log(JSON.parse(s).hash))"
}

echo "Extracting build archive..."
EXTRACT_DIR="builds/dev-sim-extracted"
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
tar -xzf "$SIM_BUILD" -C "$EXTRACT_DIR"
APP_PATH=$(find "$EXTRACT_DIR" -name "*.app" -maxdepth 1 | head -1)

echo "Installing on booted simulator..."
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
  echo "No simulator booted — booting $UDID..."
  xcrun simctl boot "$UDID"
  open -a Simulator
  sleep 3
fi
xcrun simctl install booted "$APP_PATH"

echo "Saving fingerprint..."
get_fingerprint > "$FP_FILE"

echo "Done — dev client installed (fingerprint: $(cat "$FP_FILE"))"
