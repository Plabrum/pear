Start the iOS Simulator dev environment.

1. Source `~/.zprofile` so Homebrew binaries are on PATH.
2. Run `cd app && npm run dev:sim` in the background (the Expo project lives in `app/` now).
3. Tail the output until the Metro bundler is ready and the dev server URL is shown.
4. Report the URL when it's available (usually http://localhost:8081).
