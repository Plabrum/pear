#!/usr/bin/env node
// Builds the JS bundle + assets that ota.yml publishes as a self-hosted OTA
// update — the non-Expo replacement for `expo export -p ios`. Uses the RN
// Community CLI's own `bundle` command (Metro + the project's babel config,
// no Expo involved), then compiles the JS to Hermes bytecode with the
// project's pinned `hermesc` binary so the output matches the `.hbc` format
// the existing OTA client (ios/Pear/OTA/UpdatesManager.swift) already expects.
//
// Usage: node scripts/export-ota-bundle.js [outDir]
// Writes <outDir>/bundle.hbc and <outDir>/assets/**. Defaults outDir to `dist`.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const APP_ROOT = path.join(__dirname, '..');
const outDir = path.resolve(APP_ROOT, process.argv[2] ?? 'dist');
const assetsDir = path.join(outDir, 'assets');

fs.rmSync(outDir, { recursive: true, force: true });
fs.mkdirSync(assetsDir, { recursive: true });

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ota-bundle-'));
const jsBundlePath = path.join(tmpDir, 'bundle.js');
const sourcemapPath = path.join(tmpDir, 'bundle.js.map');
const hbcBundlePath = path.join(outDir, 'bundle.hbc');

console.log('Bundling JS with react-native bundle...');
execFileSync(
  'npx',
  [
    'react-native',
    'bundle',
    '--platform',
    'ios',
    '--dev',
    'false',
    '--minify',
    'true',
    '--entry-file',
    'index.js',
    '--bundle-output',
    jsBundlePath,
    '--sourcemap-output',
    sourcemapPath,
    '--assets-dest',
    assetsDir,
  ],
  { cwd: APP_ROOT, stdio: 'inherit' }
);

const hermesc = path.join(
  APP_ROOT,
  'node_modules/hermes-compiler/hermesc',
  process.platform === 'darwin' ? 'osx-bin' : 'linux64-bin',
  'hermesc'
);

console.log('Compiling to Hermes bytecode...');
execFileSync(hermesc, ['-emit-binary', '-out', hbcBundlePath, jsBundlePath], {
  cwd: APP_ROOT,
  stdio: 'inherit',
});

fs.rmSync(tmpDir, { recursive: true, force: true });

console.log(`Wrote ${hbcBundlePath} and assets to ${assetsDir}`);
