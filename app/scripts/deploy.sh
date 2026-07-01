#!/bin/bash
# deploy.sh — OTA update if JS-only changes, full EAS build if native changed
set -e

CHANNEL=${1:-production}
FP_FILE=".build-fingerprint"

get_fingerprint() {
  npx expo-updates fingerprint:generate --platform ios 2>/dev/null \
    | node -e "let s=''; process.stdin.on('data',d=>s+=d); process.stdin.on('end',()=>console.log(JSON.parse(s).hash))"
}

echo "Generating project fingerprint..."
CURRENT=$(get_fingerprint)

if [ -z "$CURRENT" ]; then
  echo "Error: Could not generate fingerprint. Is expo-updates installed?"
  exit 1
fi

if [ -f "$FP_FILE" ] && [ "$(cat "$FP_FILE")" = "$CURRENT" ]; then
  echo "No native changes detected."
  echo ""
  read -p "OTA update message: " MSG
  MSG=${MSG:-"update"}
  echo ""
  echo "Pushing OTA update to channel '$CHANNEL'..."
  eas update --channel "$CHANNEL" --message "$MSG"
  echo ""
  echo "Done. Users on the '$CHANNEL' channel will receive the update on next launch."
else
  echo "Native changes detected (fingerprint changed)."
  echo ""
  echo "Running full EAS build for production..."
  eas build --platform ios --profile production
  echo "$CURRENT" > "$FP_FILE"
  echo ""
  read -p "Submit to App Store now? (y/N) " SUBMIT
  if [[ "$SUBMIT" =~ ^[Yy]$ ]]; then
    npm run submit:local
  else
    echo "Skipped submit. Run 'npm run submit:local' when ready."
  fi
fi
