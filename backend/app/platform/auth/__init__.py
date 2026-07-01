"""STUB authentication layer (Phase 2).

This package implements a *temporary* auth surface that mirrors the current Hono
`authMiddleware`: a Bearer JWT is decoded (NOT signature-verified) and a minimal
`StubUser` is built from the token's `sub` claim. It exists so the platform can
boot end-to-end (actions router guard, `ActionDeps.user`, RLS `app.user_id` GUC)
before the real self-hosted auth provider lands.

TODO(Phase 4): replace `StubAuthMiddleware` with real ES256 signature
verification (config.JWT_PUBLIC_KEY), proper session/role resolution from the
users table, and the enforced `role = authenticated` RLS floor.
"""
