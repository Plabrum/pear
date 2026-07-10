from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.domain.contacts.models import Contact, WingpersonInviteToken
from app.utils.sqids import Sqid
from app.utils.tokens import hash_bearer_token


class ContactService:
    """Mint/preview/finalize wingperson-invite tokens. Mirrors `AuthService`'s
    magic-link token pattern (`app/platform/auth/service.py`).

    Deliberate divergence: verify and consume are split into `preview_invite_token`
    (read-only, repeatable) and `finalize_invite_token` (single-use, stamps
    `used_at`), whereas magic-link collapses both into one `consume_magic_link`
    call. A wingperson invite is often opened before the invitee has an account to
    accept with — the invite-preview screen (fetch the dater's name to show a
    confirm step) may be hit multiple times before `AcceptInviteByToken` actually
    finalizes it, so preview must not burn the token's single use.
    """

    def __init__(self, db: AsyncSession, config: Config):
        self.db = db
        self.config = config

    def _hash_token(self, token: str) -> str:
        return hash_bearer_token(self.config.SECRET_KEY, token)

    async def issue_invite_token(self, contact_id: Sqid) -> str:
        """Mint a single-use token bound to `contact_id`, persist its hash, return the raw token.

        The raw token is returned to the caller exactly once (to put in the SMS/share
        link) and never stored — only its `_hash_token` lands in `wingperson_invite_tokens`.
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self.config.WINGPERSON_INVITE_TTL_SECONDS)
        self.db.add(
            WingpersonInviteToken(token_hash=self._hash_token(token), contact_id=contact_id, expires_at=expires_at)
        )
        await self.db.flush()
        return token

    async def preview_invite_token(self, token: str) -> Contact | None:
        """Validate a token and return its `Contact` without consuming it.

        Returns `None` for unknown / already-finalized / expired tokens. Read-only —
        safe to call repeatedly (e.g. every time the invite screen mounts).
        """
        result = await self.db.execute(
            select(WingpersonInviteToken).where(
                WingpersonInviteToken.token_hash == self._hash_token(token),
                WingpersonInviteToken.used_at.is_(None),
                WingpersonInviteToken.expires_at > datetime.now(UTC),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return await self.db.get(Contact, row.contact_id)

    async def finalize_invite_token(self, token: str) -> Sqid | None:
        """Atomically consume a token: return its `contact_id` once, then never again.

        Returns `None` for unknown / already-consumed / expired tokens. The row is
        locked `FOR UPDATE` so a concurrent double-submit serializes to one winner.
        """
        result = await self.db.execute(
            select(WingpersonInviteToken)
            .where(
                WingpersonInviteToken.token_hash == self._hash_token(token),
                WingpersonInviteToken.used_at.is_(None),
                WingpersonInviteToken.expires_at > datetime.now(UTC),
            )
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.used_at = datetime.now(UTC)
        await self.db.flush()
        return row.contact_id
