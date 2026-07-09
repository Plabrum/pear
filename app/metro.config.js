const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config');
const { withNativeWind } = require('nativewind/metro');

const config = getDefaultConfig(__dirname);

// Track B keeps the Expo-aware babel transformer even though the rest of the
// Metro config is now the plain React Native default — expo-router (removed
// in Track C) is threaded through babel-preset-expo via the caller object
// only @expo/metro-config's transformer supplies, and its require.context
// calls need unstable_allowRequireContext.
const withExpoRouterCompat = mergeConfig(config, {
  // transformerPath (top-level, not transformer.*) is what NativeWind's own
  // Metro wrapper falls back to for any .css file that isn't the designated
  // `input` below (e.g. @expo/log-box's internal CSS-module files) — without
  // it those get handed to metro's plain JS transform worker and fail to
  // parse as CSS.
  transformerPath: require.resolve('@expo/metro-config/build/transform-worker/transform-worker'),
  transformer: {
    babelTransformerPath: require.resolve('@expo/metro-config/build/babel-transformer'),
    unstable_allowRequireContext: true,
  },
});

module.exports = withNativeWind(withExpoRouterCompat, {
  input: './global.css',
});
