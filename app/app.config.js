const { version } = require('./package.json');

module.exports = {
  expo: {
    name: 'Pear',
    slug: 'wingmate',
    version,
    orientation: 'portrait',
    icon: './assets/images/icon.png',
    scheme: 'pear',
    userInterfaceStyle: 'light',
    newArchEnabled: true,
    ios: {
      supportsTablet: true,
      bundleIdentifier: 'com.plabrum.wingmate',
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
    ],
    experiments: {
      typedRoutes: true,
    },
    extra: {
      router: {},
      eas: {
        projectId: 'ce961544-87fc-4eb0-8168-3c7cd646d58e',
      },
    },
    owner: 'plab99',
    updates: {
      url: 'https://u.expo.dev/ce961544-87fc-4eb0-8168-3c7cd646d58e',
    },
    runtimeVersion: {
      policy: 'fingerprint',
    },
  },
};
