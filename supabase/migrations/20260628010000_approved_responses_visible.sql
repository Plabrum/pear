-- Approved prompt responses should be visible to swipers viewing the profile.
-- The existing SELECT policy only allows the response author or the dating
-- profile owner to see responses. This adds a permissive policy so that any
-- authenticated user can see responses that have been approved by the profile
-- owner — the approval step is the explicit opt-in for public visibility.
create policy "Approved prompt responses are visible to all authenticated users"
  on public.prompt_responses for select to authenticated
  using (is_approved = true);
