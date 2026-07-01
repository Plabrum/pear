#!/bin/zsh
# Xcode Cloud post-clone hook. Runs after repo clone, before the archive build.
# CI_PRIMARY_REPOSITORY_PATH is the repo root (monorepo) — the Expo app lives in app/.
set -eo pipefail

cd "$CI_PRIMARY_REPOSITORY_PATH/app"

# Xcode Cloud images ship Homebrew but not Node/npm — install it before use.
echo "ci_post_clone: brew install node"
brew install node

echo "ci_post_clone: npm ci"
npm ci

echo "ci_post_clone: pod install"
cd ios
pod install
