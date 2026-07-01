"""Auth-layer enums.

`AuthProvider` is the discriminator on `auth_identities` — which external login
method minted an identity. Stored as TEXT via `TextEnum` (member *values* are the
lowercase provider names so the DB rows read `phone` / `apple` / `email`, matching
the migration-plan contract and what `find_or_create_identity` looks up by).
"""

from enum import Enum


class AuthProvider(Enum):
    PHONE = "phone"
    APPLE = "apple"
    EMAIL = "email"
