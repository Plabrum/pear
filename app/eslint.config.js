const { defineConfig } = require('eslint/config');
const reactNativeConfig = require('@react-native/eslint-config/flat');

module.exports = defineConfig([
  reactNativeConfig,
  {
    ignores: ['dist/*'],
  },
  {
    // eslint-plugin-ft-flow (Flow, not used in this TypeScript project) is
    // incompatible with ESLint 9's flat-config rule API — disable its rules
    // rather than pull in an ESLint 8 downgrade for an unused language.
    files: ['**/*.js'],
    rules: {
      'ft-flow/define-flow-type': 'off',
      'ft-flow/use-flow-type': 'off',
    },
  },
]);
