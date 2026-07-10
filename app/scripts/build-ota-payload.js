// Turns the output of scripts/export-ota-bundle.js (a Hermes bundle + an
// assets directory) into the `POST /updates/publish` body
// backend/app/platform/updates/schemas.py's `PublishUpdateRequest` expects.
//
// Walks the assets directory recursively and re-hashes every file (md5 ->
// `key`, so repeat assets across updates share a client cache entry;
// sha256/base64url -> `hash`, what the client verifies against), rewriting
// each path as an absolute URL under ASSET_BASE_URL (S3 direct or CloudFront,
// whichever `ota.yml` resolved).
//
// Usage: node build-ota-payload.js <bundle-path> <assets-dir> <asset-base-url> <runtime-version> <channel> <platform>
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

// Recursively lists every file under `dir`, returning paths relative to `dir`
// (POSIX-style, for use as URL path segments).
function listFilesRecursive(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const absPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...listFilesRecursive(absPath).map((relPath) => `${entry.name}/${relPath}`));
    } else {
      results.push(entry.name);
    }
  }
  return results;
}

function main() {
  const [bundlePath, assetsDir, assetBaseUrl, runtimeVersion, channel, platform] =
    process.argv.slice(2);
  if (!bundlePath || !assetsDir || !assetBaseUrl || !runtimeVersion || !channel || !platform) {
    console.error(
      'Usage: node build-ota-payload.js <bundle-path> <assets-dir> <asset-base-url> <runtime-version> <channel> <platform>'
    );
    process.exit(1);
  }

  const { key: bundleKey, hash: bundleHash } = hashFile(bundlePath);
  const bundleName = path.basename(bundlePath);

  const launchAsset = {
    key: bundleKey,
    contentType: 'application/javascript',
    url: `${assetBaseUrl}/${bundleName}`,
    hash: bundleHash,
  };

  const assets = listFilesRecursive(assetsDir).map((relPath) => {
    const absPath = path.join(assetsDir, relPath);
    const { key, hash } = hashFile(absPath);
    const ext = path.extname(relPath);
    return {
      key,
      contentType: contentTypeFor(ext),
      url: `${assetBaseUrl}/assets/${relPath}`,
      hash,
      fileExtension: ext,
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
