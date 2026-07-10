from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.auth.enums import AuthProvider
from app.platform.base.models import BaseDBModel
from app.platform.base.rls import Anyone, RLSScopedMixin
from app.utils.sqids import Sqid, SqidType
from app.utils.textenum import TextEnum


class AuthIdentity(BaseDBModel):
    """An external login method resolving to a profile."""

    __tablename__ = "auth_identities"
    __table_args__ = (sa.UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_provider_subject"),)

    provider: Mapped[AuthProvider] = mapped_column(TextEnum(AuthProvider), nullable=False)
    # apple -> Apple stable `sub`; email -> normalized email.
    provider_subject: Mapped[str] = mapped_column(sa.Text, nullable=False)
    profile_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Only ever populated on `provider == AuthProvider.APPLE` rows — the refresh
    # token used to revoke the user's Apple Sign-In grant on account deactivation
    # (App Store Guideline 5.1.1(v)). Stored as plain text: no encryption-at-rest
    # helper exists in the codebase today, and adding one for a single column would
    # be new infrastructure for this pass — a deliberate MVP tradeoff.
    apple_refresh_token: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


# Bearer-secret table: mint + consume both run UNAUTHENTICATED (no app.user_id), and
# the consume looks the row up by an unguessable token_hash. The real floor is the
# HMAC-hashed secret, not the actor — so the policies are permissive (`true`). RLS
# stays FORCE-enabled so the table is never an accidental hole. No DELETE granted.
class MagicLinkToken(BaseDBModel, RLSScopedMixin(read=Anyone, edit={"INSERT": Anyone, "UPDATE": Anyone})):
    """A single-use, TTL-bound email magic-link token.

    Only the HMAC-SHA256 *hash* of the raw token is stored — the raw token lives
    solely in the emailed link, so a DB read alone can't be replayed. Single-use is
    enforced by stamping `used_at` on consume; expiry by `expires_at`. The row is
    looked up by `token_hash` on the unauthenticated verify path, so it is a
    bearer-secret table (see the `magic_link_tokens` RLS policies).
    """

    __tablename__ = "magic_link_tokens"

    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, nullable=False)
    # The normalized email the token authenticates; becomes the EMAIL identity subject.
    email: Mapped[str] = mapped_column(sa.Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=None)
