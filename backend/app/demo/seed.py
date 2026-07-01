# Populate the local dev database with a logged-in-able dev user plus a feed of
# fake daters, wingpeople and matches.
#
# Reuses the polyfactory factories from tests/factories/ for model construction,
# so "what a valid row looks like" stays defined in one place. The factories lean
# on faker for names/bios/answers — this module only pins the fields that matter
# for the demo (states, role/gender wiring, FKs) and the relationships between rows.
#
# Must run under a system-mode session (RLS bypassed): see app/platform/queue/run_fixtures.py.

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path

import httpx
from faker import Faker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.domain.dating_profiles.enums import City, Interest, Religion
from app.domain.decisions.enums import DecisionState
from app.domain.profiles.enums import Gender, UserRole
from app.domain.profiles.models import Profile
from app.domain.prompts.models import PromptTemplate
from app.platform.auth.enums import AuthProvider
from app.platform.auth.models import AuthIdentity
from app.platform.media.client import BaseMediaClient, build_media_client
from app.platform.media.models import Media
from app.platform.media.service import build_media_key

logger = logging.getLogger(__name__)
_fake = Faker()

# Make tests/factories importable when run as a script (mirrors how the test
# suite imports them); the factories are the single definition of a valid row.
_backend_root = Path(__file__).resolve().parent.parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from tests.factories import (  # noqa: E402
    ContactFactory,
    DatingProfileFactory,
    DecisionFactory,
    MatchFactory,
    MediaFactory,
    MessageFactory,
    ProfileFactory,
    ProfilePhotoFactory,
    ProfilePromptFactory,
)

# Email markers the wipe step keys off — anything seeded is logged in under one of
# these so a re-seed can cleanly remove the prior run. Keep in sync with wipe.py.
DEV_EMAIL = "dev@local.test"
SEED_EMAIL_DOMAIN = "@seed.pear.test"

_NUM_DATERS = 50
_NUM_WINGERS = 3
_PROMPTS_PER_PROFILE = 3
_PHOTOS_PER_PROFILE = 2

# The discover feed is same-city only (DatingProfile.city == viewer.city), so the
# whole demo pool lives in one city — otherwise random per-profile cities split the
# dev user's feed down to a handful of candidates and discover looks empty.
_SEED_CITY = City.NEW_YORK


def _interested_in(gender: Gender) -> list[Gender]:
    match gender:
        case Gender.MALE:
            return [Gender.FEMALE]
        case Gender.FEMALE:
            return [Gender.MALE]
        case Gender.NON_BINARY:
            return [Gender.MALE, Gender.FEMALE]


def _random_gender() -> Gender:
    # Mostly binary with a Non-Binary minority — a realistic spread that still
    # leaves the dev user (male, seeking female) a well-populated feed.
    return random.choices([Gender.MALE, Gender.FEMALE, Gender.NON_BINARY], weights=[47, 47, 6])[0]


def _first_name(gender: Gender) -> str:
    """A gender-matched first name, so the name reads consistently with the face."""
    match gender:
        case Gender.MALE:
            return _fake.first_name_male()
        case Gender.FEMALE:
            return _fake.first_name_female()
        case Gender.NON_BINARY:
            return _fake.first_name_nonbinary()


def _portrait_url(gender: Gender, index: int) -> str:
    """A high-res, gender-matched portrait from xsgames.co.

    `avatar.php?g=male|female` serves a large AI-generated face matched to the
    requested gender. The endpoint returns a random face per request, so we append
    a per-profile cache-buster (`&seed=<index>`) to keep distinct daters distinct.
    Non-binary profiles alternate gender deterministically by index.
    """
    match gender:
        case Gender.MALE:
            g = "male"
        case Gender.FEMALE:
            g = "female"
        case Gender.NON_BINARY:
            g = "male" if index % 2 == 0 else "female"
    return f"https://xsgames.co/randomusers/avatar.php?g={g}&seed={index}"


async def _seed_portrait_media(
    session: AsyncSession,
    *,
    owner_id: int,
    gender: Gender,
    index: int,
    media_client: BaseMediaClient,
    http: httpx.AsyncClient,
) -> Media:
    """Download a high-res gendered portrait and store its bytes in object storage,
    returning a READY Media that points at the stored key.

    The bytes are fetched once and persisted, so the stored face is stable even though
    the source endpoint returns a random portrait per request. On any network failure
    we fall back to storing the source URL as the key — `LocalMediaClient` serves that
    by reference, so seeding still works offline.
    """
    url = _portrait_url(gender, index)
    key = build_media_key(owner_id, "photo.jpg")
    try:
        resp = await http.get(url, follow_redirects=True)
        resp.raise_for_status()
        await media_client.upload(key, resp.content, content_type="image/jpeg")
    except httpx.HTTPError as exc:
        logger.warning("[seed] portrait fetch failed (%s); falling back to URL by reference", exc)
        key = url

    media = await MediaFactory.create_async(session, owner_id=owner_id, file_key=key)
    # Bytes live under `key` itself (a .jpg), so point the servable key there rather
    # than the factory's default `.webp` processed key. A URL fallback is served verbatim.
    if not key.startswith("http"):
        media.processed_key = key
    return media


async def _identify(session: AsyncSession, profile: Profile, email: str) -> None:
    """Attach an EMAIL auth identity so this profile is logged-in-able via magic link."""
    session.add(AuthIdentity(provider=AuthProvider.EMAIL, provider_subject=email, profile_id=profile.id))
    await session.flush()


async def _make_dater(
    session: AsyncSession,
    *,
    email: str,
    templates: list[PromptTemplate],
    media_client: BaseMediaClient,
    http: httpx.AsyncClient,
    gender: Gender | None = None,
    index: int = 0,
    with_photos: bool = True,
) -> Profile:
    """A dater: profile + dating profile + a few prompts + (optionally) photos.

    `index` only varies which portrait the photos point at, so distinct daters get
    distinct faces.
    """
    gender = gender or _random_gender()
    profile = await ProfileFactory.create_async(
        session, state=UserRole.DATER, gender=gender, chosen_name=_first_name(gender)
    )
    await _identify(session, profile, email)

    dating_profile = await DatingProfileFactory.create_async(
        session,
        user_id=profile.id,
        interested_gender=_interested_in(gender),
        religion=random.choice(list(Religion)),
        interests=random.sample(list(Interest), k=random.randint(3, 5)),
        city=_SEED_CITY,
    )

    for template in random.sample(templates, k=min(_PROMPTS_PER_PROFILE, len(templates))):
        await ProfilePromptFactory.create_async(
            session,
            dating_profile_id=dating_profile.id,
            owner_id=profile.id,
            prompt_template_id=template.id,
        )

    if with_photos:
        for order in range(_PHOTOS_PER_PROFILE):
            media = await _seed_portrait_media(
                session,
                owner_id=profile.id,
                gender=gender,
                index=index * _PHOTOS_PER_PROFILE + order,
                media_client=media_client,
                http=http,
            )
            await ProfilePhotoFactory.create_async(
                session,
                dating_profile_id=dating_profile.id,
                owner_id=profile.id,
                media_id=media.id,
                display_order=order,
            )

    return profile


async def seed_dev_fixtures(session: AsyncSession) -> Profile:
    """Seed the dev user and a surrounding feed of daters, wingpeople and matches.

    Returns the dev Profile. Assumes a clean slate (run wipe first) and a session
    already in system mode so RLS-forced inserts succeed.
    """
    templates = list((await session.execute(select(PromptTemplate))).scalars())
    if not templates:
        raise RuntimeError("No prompt_templates found — run `just db-upgrade` first (templates ship in a migration).")

    media_client = build_media_client(config)
    async with httpx.AsyncClient(timeout=30.0) as http:
        # ── Dev user (logged-in-able as dev@local.test via the magic-link flow) ──────
        dev = await _make_dater(
            session, email=DEV_EMAIL, templates=templates, gender=Gender.MALE, media_client=media_client, http=http
        )
        logger.info("Created dev user (id=%s, login via magic link to %s)", dev.id, DEV_EMAIL)

        # ── 50 daters, faker-generated ───────────────────────────────────────────────
        daters: list[Profile] = []
        for i in range(_NUM_DATERS):
            dater = await _make_dater(
                session,
                email=f"seed.dater.{i}{SEED_EMAIL_DOMAIN}",
                templates=templates,
                index=i,
                media_client=media_client,
                http=http,
            )
            daters.append(dater)
        logger.info("Created %d daters", len(daters))

    # ── Likes-you feed: half the daters approve the dev user (no reciprocation, so
    #    they surface as incoming likes rather than matches) ──────────────────────
    likers = daters[: _NUM_DATERS // 2]
    for liker in likers:
        await DecisionFactory.create_async(
            session,
            actor_id=liker.id,
            recipient_id=dev.id,
            state=DecisionState.APPROVED,
        )
    logger.info("%d daters liked the dev user", len(likers))

    # ── Wingpeople: wingers winging FOR the dev user ─────────────────────────────
    for i in range(_NUM_WINGERS):
        winger_gender = _random_gender()
        winger = await ProfileFactory.create_async(
            session, state=UserRole.WINGER, gender=winger_gender, chosen_name=_first_name(winger_gender)
        )
        await _identify(session, winger, f"seed.winger.{i}{SEED_EMAIL_DOMAIN}")
        await ContactFactory.create_async(
            session,
            user_id=dev.id,
            phone_number=winger.phone_number or "+15550000000",
            winger_id=winger.id,
        )
    logger.info("Created %d wingpeople for the dev user", _NUM_WINGERS)

    # ── Dev user is also a winger for two daters ─────────────────────────────────
    for dater in daters[:2]:
        await ContactFactory.create_async(
            session,
            user_id=dater.id,
            phone_number=dater.phone_number or "+15550000000",
            winger_id=dev.id,
        )
    logger.info("Dev user is winging for 2 daters")

    # ── A couple of real matches (mutual approval) with an opening message ───────
    for dater in daters[_NUM_DATERS // 2 : _NUM_DATERS // 2 + 2]:
        await DecisionFactory.create_async(
            session, actor_id=dev.id, recipient_id=dater.id, state=DecisionState.APPROVED
        )
        await DecisionFactory.create_async(
            session, actor_id=dater.id, recipient_id=dev.id, state=DecisionState.APPROVED
        )
        lo, hi = sorted([dev.id, dater.id])
        match = await MatchFactory.create_async(session, user_a_id=lo, user_b_id=hi)
        await MessageFactory.create_async(session, match_id=match.id, sender_id=dater.id)
    logger.info("Created 2 matches with opening messages")

    return dev
