from __future__ import annotations

from alembic_utils.pg_policy import PGPolicy

from app.domain.contacts.enums import WingpersonStatus
from app.platform.base.models import BaseDBModel
from app.platform.base.rls_mixins import RLS_POLICY_REGISTRY

# DB literal for an active wing relationship (TextEnum stores `.name` => 'ACTIVE').
_ACTIVE = WingpersonStatus.ACTIVE.name

# Tables that must have RLS enabled+forced. `prompt_templates` is included even
# though its only policy is `using (true)` — the SQL still enables RLS on it.
# `profile_photos` and `profile_prompts` are NOT here: they enroll for RLS via
# their mixins (UserScopedMixin / WingpersonScopedMixin record them in
# `metadata.info["rls"]`); we only attach a supplementary public-SELECT policy.
#
# `profiles` is deliberately NOT here: the root identity table carries no RLS.
# Profiles are world-readable anyway, and a row's scope is only knowable after its
# id exists — forcing RLS here would require the unauthenticated first-login
# bootstrap to "become" a user before that user exists. We leave the identity table
# open and rely on the app layer (handlers only ever update the authenticated
# principal's own row) plus the relationship-scoped child tables (dating_profiles,
# matches, messages, …) for the real floor.
_RLS_TABLES = (
    "dating_profiles",
    "prompt_templates",
    "prompt_responses",
    "contacts",
    "decisions",
    "matches",
    "messages",
    "profile_reports",
    "media",
    "magic_link_tokens",
)


def _policy(table: str, signature: str, definition: str) -> PGPolicy:
    return PGPolicy(
        schema="public",
        signature=signature,
        on_entity=f"public.{table}",
        definition=definition.strip(),
    )


# ── profiles ─────────────────────────────────────────────────────────────────
# The root identity table carries NO RLS — see `_RLS_TABLES` above. No policies are
# defined here; access is governed at the app layer.


# ── dating_profiles ──────────────────────────────────────────────────────────
# Select an active profile or your own; insert/update/delete your own.
_DATING_PROFILES = [
    _policy(
        "dating_profiles",
        "dating_profiles_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (public.is_system_mode() OR (is_active = true OR user_id = public.current_user_id()))
        """,
    ),
    _policy(
        "dating_profiles",
        "dating_profiles_insert",
        """
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (public.is_system_mode() OR (user_id = public.current_user_id()))
        """,
    ),
    _policy(
        "dating_profiles",
        "dating_profiles_update",
        """
        AS PERMISSIVE
        FOR UPDATE
        TO pear_app
        USING (public.is_system_mode() OR (user_id = public.current_user_id()))
        """,
    ),
    _policy(
        "dating_profiles",
        "dating_profiles_delete",
        """
        AS PERMISSIVE
        FOR DELETE
        TO pear_app
        USING (public.is_system_mode() OR (user_id = public.current_user_id()))
        """,
    ),
]


# ── profile_photos ───────────────────────────────────────────────────────────
# The owner/active-winger floor (SELECT/INSERT/UPDATE/DELETE) is the mixin's
# `wingperson_scope_policy` (WingpersonScopedMixin, owner_column="owner_id"). This
# supplementary SELECT broadens read visibility the floor doesn't cover: any viewer
# may read an APPROVED photo on an ACTIVE dating profile (discover/matches), and a
# suggester may read their own (possibly still-pending) suggestion.
_PROFILE_PHOTOS = [
    _policy(
        "profile_photos",
        "profile_photos_public_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (
          profile_photos.suggester_id = public.current_user_id()
          OR EXISTS (
            SELECT 1 FROM public.dating_profiles dp
            WHERE dp.id = profile_photos.dating_profile_id
              AND dp.is_active = true
              AND profile_photos.approved_at IS NOT NULL
          )
        )
        """,
    ),
]


# ── prompt_templates ─────────────────────────────────────────────────────────
# Readable by any authenticated user (seed data).
_PROMPT_TEMPLATES = [
    _policy(
        "prompt_templates",
        "prompt_templates_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (true)
        """,
    ),
]


# ── profile_prompts ──────────────────────────────────────────────────────────
# The owner floor (SELECT/INSERT/UPDATE/DELETE) is the mixin's `user_scope_policy`
# (UserScopedMixin, user_id_column="owner_id"). This supplementary SELECT broadens
# read visibility the floor doesn't cover: any viewer may read a prompt on an ACTIVE
# dating profile (discover/matches render other daters' prompts).
_PROFILE_PROMPTS = [
    _policy(
        "profile_prompts",
        "profile_prompts_public_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (
          EXISTS (
            SELECT 1 FROM public.dating_profiles dp
            WHERE dp.id = profile_prompts.dating_profile_id
              AND dp.is_active = true
          )
        )
        """,
    ),
]


# ── prompt_responses ─────────────────────────────────────────────────────────
# Two-party row (author `user_id` + denormalized `profile_owner_id`), so no mixin
# fits — bespoke, but now flat column compares (no joins). Visible to author or
# profile owner; insert as self; only the profile owner can update (approval).
_PROMPT_RESPONSES = [
    _policy(
        "prompt_responses",
        "prompt_responses_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (public.is_system_mode() OR (
          user_id = public.current_user_id()
          OR profile_owner_id = public.current_user_id()
        ))
        """,
    ),
    _policy(
        "prompt_responses",
        "prompt_responses_insert",
        """
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (public.is_system_mode() OR (user_id = public.current_user_id()))
        """,
    ),
    _policy(
        "prompt_responses",
        "prompt_responses_update",
        """
        AS PERMISSIVE
        FOR UPDATE
        TO pear_app
        USING (public.is_system_mode() OR (profile_owner_id = public.current_user_id()))
        """,
    ),
]


# ── contacts ─────────────────────────────────────────────────────────────────
# Party-to (dater OR winger) select/update; dater-only insert/delete.
_CONTACTS = [
    _policy(
        "contacts",
        "contacts_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (public.is_system_mode() OR (user_id = public.current_user_id() OR winger_id = public.current_user_id()))
        """,
    ),
    _policy(
        "contacts",
        "contacts_insert",
        """
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (public.is_system_mode() OR (user_id = public.current_user_id()))
        """,
    ),
    _policy(
        "contacts",
        "contacts_update",
        """
        AS PERMISSIVE
        FOR UPDATE
        TO pear_app
        USING (public.is_system_mode() OR (user_id = public.current_user_id() OR winger_id = public.current_user_id()))
        """,
    ),
    _policy(
        "contacts",
        "contacts_delete",
        """
        AS PERMISSIVE
        FOR DELETE
        TO pear_app
        USING (public.is_system_mode() OR (user_id = public.current_user_id()))
        """,
    ),
]


# ── decisions ────────────────────────────────────────────────────────────────
# Visible to actor/recipient/suggester; insert as actor OR as an active
# wingperson on the dater's behalf; actor-only update. The active-wingperson check
# compares against the `TextEnum` name (`'{_ACTIVE}'`, i.e. WingpersonStatus.ACTIVE.name).
_DECISIONS = [
    _policy(
        "decisions",
        "decisions_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (public.is_system_mode() OR (
          actor_id = public.current_user_id()
          OR recipient_id = public.current_user_id()
          OR suggested_by = public.current_user_id()
        ))
        """,
    ),
    _policy(
        "decisions",
        "decisions_insert",
        f"""
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (public.is_system_mode() OR (
          actor_id = public.current_user_id()
          OR (
            suggested_by = public.current_user_id()
            AND EXISTS (
              SELECT 1 FROM public.contacts c
              WHERE c.user_id = decisions.actor_id
                AND c.winger_id = public.current_user_id()
                AND c.wingperson_status = '{_ACTIVE}'
            )
          )
        ))
        """,
    ),
    _policy(
        "decisions",
        "decisions_update",
        """
        AS PERMISSIVE
        FOR UPDATE
        TO pear_app
        USING (public.is_system_mode() OR (actor_id = public.current_user_id()))
        """,
    ),
]


# ── matches ──────────────────────────────────────────────────────────────────
# Participant-only select.
#
# Inserts are server-side: match creation runs as a SYSTEM operation (the
# worker/queue path sets `app.is_system_mode = true`). The INSERT policy therefore
# permits *only* system mode — an ordinary user (escape off) can never forge a
# match row. There is intentionally no user branch.
_MATCHES = [
    _policy(
        "matches",
        "matches_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (public.is_system_mode() OR (
          user_a_id = public.current_user_id() OR user_b_id = public.current_user_id()
        ))
        """,
    ),
    _policy(
        "matches",
        "matches_insert",
        """
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (public.is_system_mode())
        """,
    ),
]


# ── messages ─────────────────────────────────────────────────────────────────
# Read/send only within a match you participate in; sender-only update (mark read).
_MESSAGES = [
    _policy(
        "messages",
        "messages_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (public.is_system_mode() OR (
          EXISTS (
            SELECT 1 FROM public.matches m
            WHERE m.id = messages.match_id
              AND (m.user_a_id = public.current_user_id() OR m.user_b_id = public.current_user_id())
          )
        ))
        """,
    ),
    _policy(
        "messages",
        "messages_insert",
        """
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (public.is_system_mode() OR (
          sender_id = public.current_user_id()
          AND EXISTS (
            SELECT 1 FROM public.matches m
            WHERE m.id = messages.match_id
              AND (m.user_a_id = public.current_user_id() OR m.user_b_id = public.current_user_id())
          )
        ))
        """,
    ),
    _policy(
        "messages",
        "messages_update",
        """
        AS PERMISSIVE
        FOR UPDATE
        TO pear_app
        USING (public.is_system_mode() OR (sender_id = public.current_user_id()))
        """,
    ),
]


# ── profile_reports ──────────────────────────────────────────────────────────
# Insert your own report only, plus a matching SELECT policy: the SQLAlchemy ORM
# emits `INSERT ... RETURNING` for server-side defaults (created_at/updated_at), and
# under FORCE RLS that RETURNING read requires a SELECT policy — without one Postgres
# rejects the insert as "new row violates row-level security policy". A reporter may
# read back their own reports (mirrors decisions_select's actor scoping).
_PROFILE_REPORTS = [
    _policy(
        "profile_reports",
        "profile_reports_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (public.is_system_mode() OR (reporter_id = public.current_user_id()))
        """,
    ),
    _policy(
        "profile_reports",
        "profile_reports_insert",
        """
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (public.is_system_mode() OR (reporter_id = public.current_user_id()))
        """,
    ),
]


# ── media ────────────────────────────────────────────────────────────────────
# Bespoke per-command policies (NOT the generic WingpersonScopedMixin FOR ALL).
#
# SELECT mirrors profile_photos visibility EXACTLY so a viewer may read a media row
# iff they may see a photo backing it: owner, the photo's suggester, or — for an
# active dating profile — an approved photo. Avatars are public-read. A matched
# viewer therefore presigns an approved photo's URL under their OWN scope (no system
# mode). The owner + their active wingperson always see their own media directly.
#
# INSERT/UPDATE/DELETE stay owner + active wingperson (the management surface): a
# winger uploads/curates media for the dater they wing.
_MEDIA = [
    _policy(
        "media",
        "media_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (public.is_system_mode()
          OR owner_id = public.current_user_id()
          OR public.is_active_wingperson(owner_id)
          OR EXISTS (
            SELECT 1
            FROM public.profile_photos pp
            JOIN public.dating_profiles dp ON dp.id = pp.dating_profile_id
            WHERE pp.media_id = media.id
              AND (
                dp.user_id = public.current_user_id()
                OR pp.suggester_id = public.current_user_id()
                OR (dp.is_active = true AND pp.approved_at IS NOT NULL)
              )
          )
          OR EXISTS (
            SELECT 1 FROM public.profiles p WHERE p.avatar_media_id = media.id
          ))
        """,
    ),
    _policy(
        "media",
        "media_insert",
        """
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (public.is_system_mode()
          OR owner_id = public.current_user_id()
          OR public.is_active_wingperson(owner_id))
        """,
    ),
    _policy(
        "media",
        "media_update",
        """
        AS PERMISSIVE
        FOR UPDATE
        TO pear_app
        USING (public.is_system_mode()
          OR owner_id = public.current_user_id()
          OR public.is_active_wingperson(owner_id))
        """,
    ),
    _policy(
        "media",
        "media_delete",
        """
        AS PERMISSIVE
        FOR DELETE
        TO pear_app
        USING (public.is_system_mode()
          OR owner_id = public.current_user_id()
          OR public.is_active_wingperson(owner_id))
        """,
    ),
]


# ── magic_link_tokens ────────────────────────────────────────────────────────
# A BEARER-SECRET table, not an actor-scoped one. Both the mint (`/magic-link/request`)
# and the consume (`/magic-link/verify`) run UNAUTHENTICATED — there is no
# `app.user_id` to scope against, and the consume must look the row up by an
# unguessable `token_hash` it cannot know in advance. So the policies are permissive
# (`USING (true)`), exactly like `prompt_templates`, but for every command. The real
# authorization floor here is the secret itself: the token is HMAC-hashed at rest, so
# even a full read of this table yields nothing replayable without the raw token (which
# lives only in the emailed link). RLS stays FORCE-enabled so the table is never an
# accidental hole; these policies just make that floor explicit.
_MAGIC_LINK_TOKENS = [
    _policy(
        "magic_link_tokens",
        "magic_link_tokens_select",
        """
        AS PERMISSIVE
        FOR SELECT
        TO pear_app
        USING (true)
        """,
    ),
    _policy(
        "magic_link_tokens",
        "magic_link_tokens_insert",
        """
        AS PERMISSIVE
        FOR INSERT
        TO pear_app
        WITH CHECK (true)
        """,
    ),
    _policy(
        "magic_link_tokens",
        "magic_link_tokens_update",
        """
        AS PERMISSIVE
        FOR UPDATE
        TO pear_app
        USING (true)
        """,
    ),
]


PEAR_RLS_POLICIES: list[PGPolicy] = [
    *_DATING_PROFILES,
    *_PROFILE_PHOTOS,
    *_PROMPT_TEMPLATES,
    *_PROFILE_PROMPTS,
    *_PROMPT_RESPONSES,
    *_CONTACTS,
    *_DECISIONS,
    *_MATCHES,
    *_MESSAGES,
    *_PROFILE_REPORTS,
    *_MEDIA,
    *_MAGIC_LINK_TOKENS,
]


def register_pear_rls() -> None:
    """Side-effect: enroll every Pear table for RLS + append all policies.

    Idempotent: guards against double-registration if imported more than once
    (e.g. by both `alembic/env.py` and a test harness).
    """
    rls_tables: set[str] = BaseDBModel.metadata.info.setdefault("rls", set())
    rls_tables.update(_RLS_TABLES)

    existing = {(p.on_entity, p.signature) for p in RLS_POLICY_REGISTRY}
    for policy in PEAR_RLS_POLICIES:
        if (policy.on_entity, policy.signature) not in existing:
            RLS_POLICY_REGISTRY.append(policy)


# Register on import — `alembic/env.py` imports this module for its side effect.
register_pear_rls()


__all__ = [
    "PEAR_RLS_POLICIES",
    "register_pear_rls",
]
