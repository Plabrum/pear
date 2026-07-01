from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.auth.enums import AuthProvider
from app.platform.base.models import BaseDBModel
from app.utils.textenum import TextEnum


class AuthIdentity(BaseDBModel):
    """An external login method resolving to a profile."""

    __tablename__ = "auth_identities"
    __table_args__ = (sa.UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_provider_subject"),)

    provider: Mapped[AuthProvider] = mapped_column(TextEnum(AuthProvider), nullable=False)
    # apple -> Apple stable `sub`; email -> normalized email.
    provider_subject: Mapped[str] = mapped_column(sa.Text, nullable=False)
    profile_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class RefreshToken(BaseDBModel):
    """A rotating, revocable refresh token (stored hashed, not raw)."""

    __tablename__ = "refresh_tokens"

    profile_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 of the raw opaque token — the raw value is returned to the client once.
    token_hash: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
    # On rotation, points at the id of the token that replaced this one (chain link).
    replaced_by: Mapped[UUID | None] = mapped_column(sa.Uuid, nullable=True)
    # Optional opaque device/user-agent descriptor for session listing / auditing.
    device_info: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
