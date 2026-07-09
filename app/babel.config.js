module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['module:@react-native/babel-preset', 'nativewind/babel'],
    plugins: [['transform-inline-environment-variables', { include: ['APP_PUBLIC_API_URL'] }]],
  };
};
