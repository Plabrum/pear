Stop the local dev environment: Expo, Supabase, and Colima.

1. Source `~/.zprofile` so Homebrew binaries are on PATH.
2. Stop the Expo web process if it is running (find and kill the process on port 8081).
3. Stop Supabase using `cd app && npm run db:down` (the Expo project lives in `app/` now). Wait for it to finish.
4. Stop Colima using `colima stop`.
5. Report when each step is complete.
