const { version } = require('./package.json');

module.exports = {
  expo: {
    name: 'Pear',
    slug: 'pear',
    version,
    orientation: 'portrait',
    icon: './assets/images/icon.png',
    scheme: 'pear',
    userInterfaceStyle: 'light',
    ios: {
      supportsTablet: true,
      bundleIdentifier: 'com.plabrum.pear',
      entitlements: {
        'com.apple.developer.applesignin': ['Default'],
        'aps-environment': 'production',
      },
      infoPlist: {
        ITSAppUsesNonExemptEncryption: false,
      },
    },
    web: {
      bundler: 'metro',
      output: 'single',
      favicon: './assets/images/favicon.png',
    },
    plugins: [
      'expo-router',
      'expo-apple-authentication',
      'expo-notifications',
      [
        'expo-splash-screen',
        {
          backgroundColor: '#F2EDDF',
        },
      ],
      '@react-native-community/datetimepicker',
      'expo-font',
      'expo-image',
      'expo-status-bar',
      'expo-web-browser',
    ],
    experiments: {
      typedRoutes: true,
      reactCompiler: true,
    },
    extra: {
      router: {},
    },
    updates: {
      url: `${process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000'}/updates/manifest`,
      // TODO(updates-key-provisioning): certs/updates-signing.pem does not exist yet — see
      // app/certs/README.md. Generate the keypair, commit only the public cert here, and keep
      // the private half in backend secrets (UPDATES_SIGNING_PRIVATE_KEY) only.
      codeSigningCertificate: './certs/updates-signing.pem',
      codeSigningMetadata: {
        keyid: 'main',
        alg: 'rsa-v1_5-sha256',
      },
    },
    runtimeVersion: {
      policy: 'fingerprint',
    },
  },
};
