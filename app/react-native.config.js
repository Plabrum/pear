module.exports = {
  dependencies: {
    // `expo` stays installed for its CLI (lint, web bundling) and JS-only utilities,
    // but its iOS podspec must not autolink — that's exactly the native Expo modules
    // layer Phase 5 of the off-Expo migration removes. Podfile no longer calls
    // use_expo_modules!, but plain `use_native_modules!` autolinking would otherwise
    // still pick up any package.json dependency that ships an iOS podspec.
    expo: {
      platforms: { ios: null },
    },
  },
};
