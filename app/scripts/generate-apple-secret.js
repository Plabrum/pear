const jwt = require('jsonwebtoken');
const fs = require('fs');

const TEAM_ID = process.env.APPLE_TEAM_ID; // e.g. ABCDE12345
const KEY_ID = process.env.APPLE_KEY_ID; // e.g. 1A2BC3D4E5
const CLIENT_ID = process.env.APPLE_CLIENT_ID; // Services ID, e.g. com.plabrum.pear.auth
const P8_PATH = process.env.APPLE_P8_PATH; // path to .p8

const privateKey = fs.readFileSync(P8_PATH, 'utf8');

const now = Math.floor(Date.now() / 1000);
const exp = now + 60 * 60 * 24 * 180; // 180 days

const token = jwt.sign(
  {
    iss: TEAM_ID,
    iat: now,
    exp,
    aud: 'https://appleid.apple.com',
    sub: CLIENT_ID,
  },
  privateKey,
  {
    algorithm: 'ES256',
    keyid: KEY_ID,
  }
);

console.log(token);
