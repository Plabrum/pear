-- Track rejection of winger-suggested photos and prompt responses

alter table profile_photos
  add column if not exists rejected_at timestamptz;

alter table prompt_responses
  add column if not exists is_rejected boolean not null default false;
