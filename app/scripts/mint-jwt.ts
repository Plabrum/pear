#!/usr/bin/env npx tsx
import jwt from 'jsonwebtoken';

const secret = process.env.SUPABASE_JWT_SECRET;
if (!secret) {
  console.error('Error: SUPABASE_JWT_SECRET must be set.');
  process.exit(1);
}

const userId = process.argv[2];
if (!userId) {
  console.error('Usage: mint-jwt.ts <user_id> [hours=24]');
  process.exit(1);
}

const hours = Number(process.argv[3] ?? 24);
const now = Math.floor(Date.now() / 1000);

const token = jwt.sign(
  {
    aud: 'authenticated',
    role: 'authenticated',
    sub: userId,
    iss: 'supabase',
    iat: now,
    exp: now + hours * 3600,
    session_id: crypto.randomUUID(),
  },
  secret,
  { algorithm: 'HS256' }
);

process.stdout.write(token);
