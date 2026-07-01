#!/bin/zsh
# Xcode Cloud post-build hook. Runs after xcodebuild completes (archive/test/build).
# Only the archive action produces a real native build worth recording — writes back
# the `@expo/fingerprint` hash of this native build to the backend so `ota.yml`'s
# fingerprint guardrail has something authoritative to compare an OTA export against
# (replaces the old vars.NATIVE_BUILD_FINGERPRINT GitHub variable, which Xcode Cloud
# had no automated way to write).
#
# Requires these set as Environment Variables on the Xcode Cloud workflow (App Store
# Connect → Xcode Cloud → workflow → Environment):
#   API_BASE_URL          — e.g. https://api.usepear.app (no trailing slash).
#   UPDATES_PUBLISH_TOKEN — same Terraform-generated bearer token ota.yml uses to call
#                            POST /updates/publish (infra/modules/ec2_stack/main.tf's
#                            aws_secretsmanager_secret.updates). Mark it "Secret" in
#                            the workflow settings so it's masked in build logs. This
#                            is a one-time paste, not a new credential to invent.
set -eo pipefail

if [[ "$CI_XCODEBUILD_ACTION" != "archive" ]]; then
  echo "ci_post_xcodebuild: action is '$CI_XCODEBUILD_ACTION', not 'archive' — skipping fingerprint write-back"
  exit 0
fi

cd "$CI_PRIMARY_REPOSITORY_PATH/app"

FINGERPRINT=$(npx expo-updates fingerprint:generate --platform ios | node -e '
  let data = "";
  process.stdin.on("data", (chunk) => (data += chunk));
  process.stdin.on("end", () => {
    const parsed = JSON.parse(data);
    process.stdout.write(parsed.hash ?? parsed.fingerprintHash ?? "");
  });
')

if [[ -z "$FINGERPRINT" ]]; then
  echo "::error::Could not compute a fingerprint for this native build — refusing to write back a blank value."
  exit 1
fi

echo "ci_post_xcodebuild: computed fingerprint ${FINGERPRINT}"

HTTP_STATUS=$(curl -sS -o /tmp/fingerprint-response.json -w '%{http_code}' \
  -X POST "${API_BASE_URL}/updates/native-build-fingerprint" \
  -H "Authorization: Bearer ${UPDATES_PUBLISH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"platform\":\"ios\",\"fingerprint\":\"${FINGERPRINT}\"}")

cat /tmp/fingerprint-response.json
if [[ "$HTTP_STATUS" -ge 300 ]]; then
  echo "::error::POST ${API_BASE_URL}/updates/native-build-fingerprint returned ${HTTP_STATUS} — this native build's fingerprint was NOT recorded. ota.yml's guardrail will keep comparing against the previous value until this is retried."
  exit 1
fi

echo "ci_post_xcodebuild: fingerprint recorded"
