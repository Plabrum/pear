#!/bin/zsh
# Xcode Cloud post-clone hook. Runs after repo clone, before the archive build.
# CI_PRIMARY_REPOSITORY_PATH is the repo root (monorepo) — the Expo app lives in app/.
set -eo pipefail

cd "$CI_PRIMARY_REPOSITORY_PATH/app"

# Xcode Cloud images ship Homebrew but not Node/npm — install it before use.
# Pinned to node@24 to match every GitHub Actions workflow (see node-version: "24"
# in .github/workflows/*.yml) — an unpinned `brew install node` resolves to
# whatever is current (26.x as of writing) and risks the same npm-ci
# lockfile-mismatch class of failure those workflows were pinned to fix.
# HOMEBREW_NO_AUTO_UPDATE skips brew's own tap-index refresh, which is the
# slowest and most hang-looking part of a cold install.
export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_INSTALL_CLEANUP=1

# Xcode Cloud's build agent can end up running this script under Rosetta 2
# (x86_64 emulation) even on arm64 hardware. A translated process hits CocoaPods'
# own Rosetta guard ("Do not use pod install from inside Rosetta2") and can fail
# TLS handshakes to cdn.cocoapods.org. Force native arm64 for everything below.
if [ "$(sysctl -in hw.optional.arm64)" = "1" ]; then
  ARCH_PREFIX=(arch -arm64)
else
  ARCH_PREFIX=()
fi

echo "ci_post_clone: brew install node@24"
"${ARCH_PREFIX[@]}" brew install node@24
export PATH="$("${ARCH_PREFIX[@]}" brew --prefix node@24)/bin:$PATH"

echo "ci_post_clone: npm ci"
"${ARCH_PREFIX[@]}" npm ci

echo "ci_post_clone: brew install xcodegen"
"${ARCH_PREFIX[@]}" brew install xcodegen

cd ios

echo "ci_post_clone: xcodegen generate"
"${ARCH_PREFIX[@]}" xcodegen generate

echo "ci_post_clone: pod install"
"${ARCH_PREFIX[@]}" pod install
