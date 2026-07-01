# Remove everything a previous fixture seed created.
#
# Seeded rows hang off profiles whose EMAIL auth identity is the dev address or a
# `@seed.pear.test` address. Deleting those profiles cascades to their dating
# profiles, photos, media, decisions, matches, messages, prompts, contacts and
# auth identities via the ON DELETE CASCADE FKs, so this only has to target the
# profiles themselves (plus the email-keyed magic-link tokens, which carry no FK).
#
# Must run under a system-mode session (RLS bypassed): see app/platform/queue/run_fixtures.py.

from __future__ import annotations

import logging

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.profiles.models import Profile
from app.platform.auth.enums import AuthProvider
from app.platform.auth.models import AuthIdentity, MagicLinkToken

from .seed import DEV_EMAIL, SEED_EMAIL_DOMAIN

logger = logging.getLogger(__name__)


async def wipe_dev_fixtures(session: AsyncSession) -> int:
    """Delete all seeded profiles (cascading to their data) and seed magic-link tokens.

    Returns the number of profiles removed.
    """
    seed_email = AuthIdentity.provider_subject.like(f"%{SEED_EMAIL_DOMAIN}")
    dev_email = AuthIdentity.provider_subject == DEV_EMAIL

    profile_ids = list(
        (
            await session.execute(
                select(AuthIdentity.profile_id).where(
                    AuthIdentity.provider == AuthProvider.EMAIL,
                    or_(seed_email, dev_email),
                )
            )
        ).scalars()
    )

    if not profile_ids:
        logger.info("No seeded profiles found — nothing to wipe")
        return 0

    await session.execute(
        delete(MagicLinkToken).where(
            or_(MagicLinkToken.email.like(f"%{SEED_EMAIL_DOMAIN}"), MagicLinkToken.email == DEV_EMAIL)
        )
    )
    # FK ON DELETE CASCADE removes the dependent rows across every domain table.
    await session.execute(delete(Profile).where(Profile.id.in_(profile_ids)))
    logger.info("Wiped %d seeded profiles (and their cascaded data)", len(profile_ids))
    return len(profile_ids)
