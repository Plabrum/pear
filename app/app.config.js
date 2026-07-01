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
      // Local dev-client builds (scripts/dev-sim.sh, PEAR_LOCAL_DEV=1) omit code signing: the
      // private key backing certs/updates-signing.pem lives only in AWS Secrets Manager (see
      // certs/README.md), so Metro can't sign dev manifests for it and expo-updates would refuse
      // to serve the client. Xcode Cloud / production builds always sign.
      ...(process.env.PEAR_LOCAL_DEV === '1'
        ? {}
        : {
            codeSigningCertificate: './certs/updates-signing.pem',
            codeSigningMetadata: {
              keyid: 'main',
              alg: 'rsa-v1_5-sha256',
            },
          }),
    },
    runtimeVersion: {
      policy: 'fingerprint',
    },
  },
};
