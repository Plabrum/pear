#!/bin/bash
set -e

MISSING=()

check() {
  if ! command -v "$1" &>/dev/null; then
    MISSING+=("$2")
  else
    echo "  ✓ $1 ($(command -v "$1"))"
  fi
}

echo "Checking local iOS build dependencies..."
check xcodebuild  "Xcode (install from App Store)"
check pod         "CocoaPods (brew install cocoapods)"
check fastlane    "Fastlane (brew install fastlane)"
check ruby        "Ruby (brew install ruby)"
check node        "Node.js (brew install node)"

if [ ${#MISSING[@]} -ne 0 ]; then
  echo ""
  echo "Missing dependencies:"
  for dep in "${MISSING[@]}"; do
    echo "  ✗ $dep"
  done
  exit 1
fi

echo ""
echo "All dependencies found."
