"""Self-hosted authentication (Phase 4).

Pear owns auth end-to-end (no Supabase): it issues + verifies its own ES256 access
tokens, runs phone OTP / Apple Sign-In / email magic-link login itself, and stores
rotating refresh tokens. The pieces:

  * `models` — `AuthIdentity` + `RefreshToken` tables; `enums.AuthProvider`.
  * `principal` — the authenticated request `User` (loaded from `profiles`).
  * `tokens.TokenService` — ES256 issue/verify + refresh rotation with reuse
    detection.
  * `service.AuthService` — identity bootstrap (`find_or_create_identity`) +
    `issue_session`.
  * `clients` — OTP (Twilio Verify / local fake) + Apple JWKS verifier (with a
    test-key injection path).
  * `middleware.JWTAuthMiddleware` — verifies the Bearer token's ES256 signature
    and attaches the verified principal; `deps.provide_current_user` builds the
    rich `User`; `guards.requires_session` gates protected routes.
  * `routes` — token-core routes (refresh / logout / me); login-method routes are
    appended by the Methods agent (see `routes.py` docstring).
"""
