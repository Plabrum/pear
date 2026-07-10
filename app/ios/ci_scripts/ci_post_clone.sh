#!/bin/zsh
# Xcode Cloud post-clone hook. Runs after repo clone, before the archive build.
# CI_PRIMARY_REPOSITORY_PATH is the repo root (monorepo) — the app lives in app/.
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
# TLS handshakes to cdn.cocoapods.org. Force native arm64 for pod install only —
# brew/npm/xcodegen must NOT be forced: this image's brew resolves to the Intel
# (/usr/local) install, whose bottles (e.g. xcodegen) come down x86_64-only, and
# `arch -arm64` on an x86_64 binary is "Bad CPU type in executable" (it blocks
# the Rosetta translation that running unforced would get for free).
if [ "$(sysctl -in hw.optional.arm64)" = "1" ]; then
  ARCH_PREFIX=(arch -arm64)
else
  ARCH_PREFIX=()
fi

echo "ci_post_clone: brew install node@24"
brew install node@24
export PATH="$(brew --prefix node@24)/bin:$PATH"

echo "ci_post_clone: npm ci"
npm ci

echo "ci_post_clone: brew install xcodegen"
brew install xcodegen

cd ios

echo "ci_post_clone: xcodegen generate"
xcodegen generate

echo "ci_post_clone: pod install"
"${ARCH_PREFIX[@]}" pod install
