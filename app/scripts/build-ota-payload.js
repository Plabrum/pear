// Turns an `expo export` output directory into the `POST /updates/publish` body
// backend/app/platform/updates/schemas.py's `PublishUpdateRequest` expects.
//
// `expo export -p ios` writes `dist/metadata.json` (Expo Updates' own export
// manifest — bundle + asset paths, already content-hashed on disk) alongside the
// files themselves. This script re-hashes each file (md5 -> `key`, so repeat
// assets across updates share a client cache entry; sha256/base64url -> `hash`,
// what the client verifies against) and rewrites the paths as absolute URLs
// under ASSET_BASE_URL (S3 direct or CloudFront, whichever `ota.yml` resolved).
//
// Usage: node build-ota-payload.js <dist-dir> <asset-base-url> <runtime-version> <channel> <platform>
// Prints the JSON payload to stdout.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const CONTENT_TYPE_BY_EXT = {
  '.js': 'application/javascript',
  '.hbc': 'application/javascript',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.json': 'application/json',
};

function contentTypeFor(ext) {
  return CONTENT_TYPE_BY_EXT[ext.toLowerCase()] ?? 'application/octet-stream';
}

function hashFile(absPath) {
  const data = fs.readFileSync(absPath);
  return {
    key: crypto.createHash('md5').update(data).digest('hex'),
    hash: crypto.createHash('sha256').update(data).digest('base64url'),
  };
}

function main() {
  const [distDir, assetBaseUrl, runtimeVersion, channel, platform] = process.argv.slice(2);
  if (!distDir || !assetBaseUrl || !runtimeVersion || !channel || !platform) {
    console.error(
      'Usage: node build-ota-payload.js <dist-dir> <asset-base-url> <runtime-version> <channel> <platform>'
    );
    process.exit(1);
  }

  const metadata = JSON.parse(fs.readFileSync(path.join(distDir, 'metadata.json'), 'utf8'));
  const platformMetadata = metadata.fileMetadata[platform];
  if (!platformMetadata) {
    console.error(`No fileMetadata for platform "${platform}" in ${distDir}/metadata.json`);
    process.exit(1);
  }

  const bundlePath = platformMetadata.bundle;
  const bundleAbsPath = path.join(distDir, bundlePath);
  const { key: bundleKey, hash: bundleHash } = hashFile(bundleAbsPath);

  const launchAsset = {
    key: bundleKey,
    contentType: 'application/javascript',
    url: `${assetBaseUrl}/${bundlePath}`,
    hash: bundleHash,
  };

  const assets = platformMetadata.assets.map((asset) => {
    const absPath = path.join(distDir, asset.path);
    const { key, hash } = hashFile(absPath);
    return {
      key,
      contentType: contentTypeFor(`.${asset.ext}`),
      url: `${assetBaseUrl}/${asset.path}`,
      hash,
      fileExtension: `.${asset.ext}`,
    };
  });

  process.stdout.write(
    JSON.stringify({
      runtimeVersion,
      channel,
      platform,
      launchAsset,
      assets,
    })
  );
}

main();
