-- Allow multiple wingers to suggest the same profile to the same dater.
--
-- Previously, unique_actor_recipient prevented more than one decisions row
-- per (actor_id, recipient_id) pair. We replace it with two partial indexes:
--   1. Actual swipe decisions (suggested_by IS NULL): still one per pair.
--   2. Winger suggestions (suggested_by IS NOT NULL): one per (actor, recipient, winger).

ALTER TABLE decisions DROP CONSTRAINT IF EXISTS unique_actor_recipient;

CREATE UNIQUE INDEX IF NOT EXISTS decisions_actor_recipient_swipe_unique
  ON decisions (actor_id, recipient_id)
  WHERE suggested_by IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS decisions_actor_recipient_winger_unique
  ON decisions (actor_id, recipient_id, suggested_by)
  WHERE suggested_by IS NOT NULL;
