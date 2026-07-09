const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env.local') });
const { getDefaultConfig } = require('@react-native/metro-config');
const { withNativeWind } = require('nativewind/metro');

const config = getDefaultConfig(__dirname);

// `@expo/metro-config` used to resolve the `@/*` -> `./*` alias (tsconfig.json
// `paths`) automatically; `@react-native/metro-config` doesn't, so replicate it
// with a resolveRequest hook.
const { resolveRequest: defaultResolveRequest } = config.resolver;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (moduleName === '@' || moduleName.startsWith('@/')) {
    const resolved = path.join(__dirname, moduleName.slice(1) || '.');
    return context.resolveRequest(context, resolved, platform);
  }
  return defaultResolveRequest
    ? defaultResolveRequest(context, moduleName, platform)
    : context.resolveRequest(context, moduleName, platform);
};

module.exports = withNativeWind(config, { input: './global.css' });
