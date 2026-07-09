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
        // react-native-image-crop-picker needs this explicitly — expo-image-picker used to
        // supply it implicitly via its own config-plugin (auto-applied through Expo
        // autolinking even though it was never listed in the `plugins` array below). That
        // implicit plugin is gone now that expo-image-picker is removed. No camera capture
        // call site exists today, so NSCameraUsageDescription is intentionally omitted.
        NSPhotoLibraryUsageDescription:
          'Pear needs access to your photos so you can add them to your profile.',
        NSContactsUsageDescription:
          'Pear needs access to your contacts so you can invite a wingperson.',
        // 'sms' lets Linking.canOpenURL('sms:') report true (invite-a-wingperson flow) —
        // without a query-schemes declaration, canOpenURL for non-http(s) schemes can
        // silently return false on iOS even when the Messages app can handle the URL.
        LSApplicationQueriesSchemes: ['sms'],
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
      // Without this, expo-updates never sends the expo-channel-name header at all, and
      // the backend's /updates/manifest route hard-requires it (400s without it) - every
      // real update check silently failed until this was added. There's no EAS Update in
      // this project, so the "channel" concept has no built-in app.config.js field (that's
      // an EAS-only construct) - requestHeaders is the actual self-hosted-server mechanism
      // for sending custom headers on every manifest request. "production" is the only
      // channel actually published to (ota.yml hardcodes it; see UpdateChannel enum).
      requestHeaders: {
        'expo-channel-name': 'production',
      },
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
