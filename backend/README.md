# backend/ — Litestar API + worker (Python)

Self-hosted backend that replaces the Supabase Edge Functions (Hono/Drizzle) stack.
Litestar + SQLAlchemy 2.0 async + Alembic + SAQ, deployed on a single EC2 box via
docker-compose. Populated across Phases 2–6 of the migration.

See `docs/migration/` for the plan. Dev commands live in the root `Justfile`
(`just install`, `just dev-backend`, `just db-start`, `just test`).
