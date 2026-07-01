from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.domain.profiles.enums import UserRole
from app.domain.profiles.models import Profile
from app.platform.auth.models import RefreshToken

_ALGORITHM = "ES256"


class TokenError(Exception):
    """Raised on any token verification / rotation failure (caller maps to 401)."""


@dataclass
class RotatedSession:
    """Result of rotating a refresh token: a fresh access+refresh pair."""

    access_token: str
    refresh_token: str
    profile_id: UUID


def hash_refresh_token(raw: str) -> str:
    """SHA-256 hex digest of a raw refresh token (what we persist + look up by)."""
    return hashlib.sha256(raw.encode()).hexdigest()


class TokenService:
    def __init__(self, db: AsyncSession, config: Config):
        self.db = db
        self.config = config

    # ── Access tokens (stateless ES256) ───────────────────────────────────────

    def issue_access_token(self, profile: Profile) -> str:
        """Mint a short-lived ES256 access token for a profile."""
        now = datetime.now(UTC)
        # `role` is the profile's dater|winger (or null before onboarding picks one).
        role = profile.role.value if isinstance(profile.role, UserRole) else None
        claims = {
            "sub": str(profile.id),
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self.config.ACCESS_TOKEN_TTL_SECONDS)).timestamp()),
            "iss": self.config.JWT_ISSUER,
            "aud": self.config.JWT_AUDIENCE,
        }
        return jwt.encode(claims, self.config.JWT_SIGNING_KEY, algorithm=_ALGORITHM)

    def verify_access_token(self, token: str) -> dict:
        """Verify signature + exp + iss/aud and return claims. Raises on failure."""
        try:
            return jwt.decode(
                token,
                self.config.JWT_PUBLIC_KEY,
                algorithms=[_ALGORITHM],
                audience=self.config.JWT_AUDIENCE,
                issuer=self.config.JWT_ISSUER,
            )
        except jwt.PyJWTError as e:
            raise TokenError(f"Invalid access token: {e}") from e

    # ── Refresh tokens (stateful, rotating, revocable) ────────────────────────

    async def mint_refresh_token(self, profile_id: UUID, *, device_info: str | None = None) -> str:
        """Create + persist a new refresh token, returning the raw value (once).

        `refresh_tokens` has no RLS, so this runs without any escape on the
        unauthenticated auth path (no `app.user_id` required).
        """
        raw = secrets.token_urlsafe(48)
        record = RefreshToken(
            profile_id=profile_id,
            token_hash=hash_refresh_token(raw),
            expires_at=datetime.now(UTC) + timedelta(seconds=self.config.REFRESH_TOKEN_TTL_SECONDS),
            revoked=False,
            device_info=device_info,
        )
        self.db.add(record)
        await self.db.flush()
        return raw

    async def _load_refresh(self, raw: str) -> RefreshToken | None:
        result = await self.db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        return result.scalar_one_or_none()

    async def _revoke_chain(self, token: RefreshToken) -> None:
        """Revoke a token and walk `replaced_by` forward, revoking the whole chain."""
        current: RefreshToken | None = token
        seen: set[UUID] = set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            current.revoked = True
            next_id = current.replaced_by
            if next_id is None:
                break
            result = await self.db.execute(select(RefreshToken).where(RefreshToken.id == next_id))
            current = result.scalar_one_or_none()
        await self.db.flush()

    async def rotate_refresh(self, raw: str, *, device_info: str | None = None) -> RotatedSession:
        """Swap a refresh token for a new access+refresh pair.

        REUSE DETECTION: a token that is already revoked (or expired) being
        presented means it was rotated/leaked — revoke the entire chain and fail.

        `refresh_tokens` has no RLS, so rotation runs without any escape.
        """
        record = await self._load_refresh(raw)
        if record is None:
            raise TokenError("Refresh token not found")

        now = datetime.now(UTC)
        if record.revoked:
            # Reuse of a rotated token: assume compromise, burn the chain.
            await self._revoke_chain(record)
            raise TokenError("Refresh token reuse detected; session revoked")
        if record.expires_at <= now:
            record.revoked = True
            await self.db.flush()
            raise TokenError("Refresh token expired")

        profile = await self.db.get(Profile, record.profile_id)
        if profile is None:
            record.revoked = True
            await self.db.flush()
            raise TokenError("Profile no longer exists")

        new_raw = await self.mint_refresh_token(record.profile_id, device_info=device_info or record.device_info)
        new_record = await self._load_refresh(new_raw)
        # Link old -> new and revoke the old (single-use rotation).
        record.revoked = True
        record.replaced_by = new_record.id if new_record is not None else None
        await self.db.flush()

        access = self.issue_access_token(profile)
        return RotatedSession(access_token=access, refresh_token=new_raw, profile_id=record.profile_id)

    async def revoke_refresh(self, raw: str) -> None:
        """Revoke a single refresh token (logout). No-op if unknown.

        `refresh_tokens` has no RLS, so revocation runs without any escape.
        """
        record = await self._load_refresh(raw)
        if record is not None:
            record.revoked = True
            await self.db.flush()
