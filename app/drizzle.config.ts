import 'dotenv/config';
import { defineConfig } from 'drizzle-kit';

const url =
  process.env.DRIZZLE_INTROSPECT_URL ?? 'postgresql://postgres:postgres@127.0.0.1:54322/postgres';

export default defineConfig({
  dialect: 'postgresql',
  schema: '../supabase/functions/api/db/schema.ts',
  out: './.drizzle',
  schemaFilter: ['public'],
  dbCredentials: { url },
  casing: 'snake_case',
});
