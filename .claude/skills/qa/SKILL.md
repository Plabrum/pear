---
name: qa
description: iOS QA playbook for the Wyng app. Use when running an exploratory QA pass against the dev-sim build, exercising a flow in the Simulator via XcodeBuildMCP, or filing reproducible bug reports as GitHub issues. Covers Metro lifecycle in headless mode, MCP-driven flow walking, dedup rules, the flow_tests.md scratchpad format, and the issue-filing template. Triggered by phrases like "QA the app", "test the discover flow", "exercise onboarding in the sim", "file a bug for X", or by the `agent-loop --role qa` headless worker.
---

# iOS QA Playbook

## What this app needs

> The Expo project now lives in `app/`. Run all `npm`/script commands from `app/` (`cd app` first).

- **Bundle id:** `com.plabrum.wingmate`
- **Pre-built sim app:** `app/builds/dev-sim.app`
- **Backend:** local Supabase stack via `cd app && npm run db:up` (idempotent)
- **Seed:** `cd app && npm run db:fixtures` (reproducible local state)
- **Bundler:** Metro on `http://localhost:8081`, started by `cd app && npm run dev:sim`
- **Backlog:** open GitHub issues on the current repo, `bug` label

## flow_tests.md — your scratchpad

`flow_tests.md` lives at the repo root, gitignored (entry already in `.gitignore`). It is the only state QA carries across sessions — a checklist of flows plus a recently-tested log.

Format:

```
# Flow tests

## Flows
- [ ] Auth · Apple Sign-In happy path
- [ ] Auth · SMS OTP happy path
- [ ] Auth · SMS OTP wrong code rejection
- [ ] Onboarding · dater role full path
- [ ] Onboarding · winger role full path
- [ ] Discover · swipe right → match overlay
- [ ] Discover · paused dating_status gate
- [ ] Matches · open match sheet, send first message
- [ ] Messages · realtime delivery, presence dot
- [ ] Wingpeople · invite flow + deep link
- [ ] WingSwipe · suggest with note
- [ ] Profile · edit about me
- [ ] Profile · upload + crop photo
- [ ] Profile · prompt picker + answer
- [ ] Push · new match notification
- [ ] Push · new message notification
- ... (expand as you discover more)

## Recently tested
- 2026-04-25 — Auth · SMS OTP happy path — passed (no issues filed)
- 2026-04-25 — Discover · swipe right → match overlay — issue #42 filed
```

Picking rules:

1. If the file is missing or empty, brainstorm the flow list from `app/app/` (expo-router routes), `CLAUDE.md`, and the data model. Cover every tab and every onboarding/auth path.
2. Pick the first unchecked flow from the top. If everything is checked, re-run the least-recently-tested flow from "Recently tested" — regressions ship constantly.
3. Skip flows that need real hardware (real APNs delivery, Twilio SMS to a real phone, Apple ID sign-in). Note "skipped — needs real device" next to the entry.

## Bring up the backend

```
cd app && npm run db:up          # idempotent; safe if already running
cd app && npm run db:fixtures    # seeds reproducible local state
```

If you need ad-hoc data beyond fixtures (a dater with N matches, etc.), use `psql postgresql://postgres:postgres@127.0.0.1:54322/postgres -c "..."` or a temp `.ts` script invoked with `npx tsx` (from `app/`). Don't commit ad-hoc seeds.

If `npm run db:up` fails outright, file ONE infrastructure issue and stop the session.

## Metro lifecycle (the headless trap)

`cd app && npm run dev:sim` (i.e. `app/scripts/dev-sim.sh`) starts Metro and never exits. If you call it foreground, your session wedges forever. Always launch detached and poll for readiness.

First check whether Metro is already running (likely — humans leave dev-sim up between sessions):

```
curl -fsS http://localhost:8081/status >/dev/null && echo "metro already up" || echo "metro down"
```

- "metro already up" → skip ahead to the simulator section.
- "metro down" → start detached and poll for up to 5 minutes:

```
nohup bash -c 'cd app && npm run dev:sim' > /tmp/dev-sim-qa.log 2>&1 & disown
for i in $(seq 1 60); do
  curl -fsS http://localhost:8081/status >/dev/null && { echo "metro up after ${i}x5s"; break; }
  sleep 5
done
curl -fsS http://localhost:8081/status >/dev/null || { echo "metro never came up"; tail -50 /tmp/dev-sim-qa.log; exit 1; }
```

If Metro never comes up, file ONE infrastructure issue with the `/tmp/dev-sim-qa.log` tail as evidence and stop. Without Metro you cannot test.

## Drive the app via XcodeBuildMCP

Use the MCP tools — don't shell out to `xcrun` for anything the MCP can do.

- `mcp__XcodeBuildMCP__list_sims` — confirm a booted simulator exists.
- `mcp__XcodeBuildMCP__install_app_sim` with `appPath: "/Users/phil/repos/wingmate/app/builds/dev-sim.app"` — re-install fresh each session for a clean slate.
- `mcp__XcodeBuildMCP__launch_app_sim` — pass `env: { EXPO_PUBLIC_DEV_AUTOFILL: "1" }` if useful.
- `mcp__XcodeBuildMCP__start_sim_log_cap` with `subsystemFilter: "app"` and `captureConsole: true` BEFORE you start exercising the flow. Save the returned `logSessionId`.
- `mcp__XcodeBuildMCP__screenshot` — capture before each interaction and after each state change.
- `mcp__XcodeBuildMCP__snapshot_ui` — get tappable element coordinates. Always snapshot before tapping; never guess coordinates.
- Tap / swipe / type via the matching XcodeBuildMCP UI tools. Look up their schemas via ToolSearch on demand.
- `mcp__XcodeBuildMCP__stop_sim_log_cap` with the `logSessionId` — at the end of the flow, get the log buffer.
- `mcp__XcodeBuildMCP__stop_app_sim` — clean teardown.

## Walk the flow

For each step in the chosen flow:

1. `snapshot_ui` → identify the next target.
2. `screenshot` → record pre-state.
3. tap / type / swipe.
4. wait briefly (1–2s for animations, longer for network).
5. `screenshot` → record post-state.
6. compare against expected behavior derived from `app/` and `components/`.

For each anomaly — visual glitch, wrong copy, missing affordance, console warning, network 4xx/5xx, slow transition (>1s in-app, >3s network), keyboard not dismissing, layout overflow, accessibility issue, anything off — capture screenshot path(s), the relevant log slice, and the exact repro steps. **One anomaly = one issue.** Don't bundle.

## Dedup before filing

Bugs we file are typically big and obvious (a screen crashes, a tab is unreachable, a flow can't complete) — assume the anomaly is real on first observation, no re-run from a fresh install needed.

Before filing, grep your earlier `gh issue list` output for keywords from your draft title. If it's already filed, `gh issue comment <num>` with the new evidence and move on — don't open a duplicate.

If something genuinely looked off in one screenshot but you can't describe a clean repro, note it in `flow_tests.md` under the flow entry and skip filing.

## File the issue

Every confirmed, deduped bug becomes a GitHub issue with the `bug` label.

Title style: `<surface> · <what's wrong>`. Examples:

- `Discover · match overlay shows blank avatar after right-swipe`
- `Onboarding · keyboard covers "Continue" on PromptsStep`

No vague titles like "bug in discover".

```
gh issue create \
  --label bug \
  --title "<surface> · <what's wrong>" \
  --body "$(cat <<'EOF'
## Flow
<which flow_tests.md entry, e.g. Discover · swipe right → match overlay>

## Steps to reproduce
1. ...
2. ...
3. ...

## Expected
<one sentence>

## Actual
<one sentence>

## Evidence
- Screenshot(s): <path or attached>
- Relevant logs:
\`\`\`
<log slice>
\`\`\`

## Environment
- Build: builds/dev-sim.app (fingerprint: <paste from .dev-sim-fingerprint>)
- Simulator: <device name + iOS version from list_sims>
- Commit: <git rev-parse --short HEAD>
EOF
)"
```

After filing, update `flow_tests.md`:

- Move the flow line under "Recently tested" with today's date and the issue numbers (e.g. `2026-04-25 — Discover · swipe right → match overlay — #42, #43`).
- If the flow exposed sub-flows you didn't enumerate, add new unchecked entries to the top section.

## Rules

- **One flow per session.** Stop after testing it and filing all issues from it. Don't chain flows.
- Never push to `main`, never open PRs, never modify app code. Only writes allowed: `flow_tests.md` (gitignored), `.gitignore` (only on first run, to add `flow_tests.md`), GitHub issues, and evidence files (screenshots, log slices, scratch notes) inside the gitignored `qa/` directory. Create `qa/` if it doesn't exist. Never write evidence to the repo root or any other tracked path.
- Never `git add`, `git commit`, or `git push`. The QA loop is read-only against the working tree apart from the writes listed above.
- Never run `npm run deploy*`, `eas submit`, `eas update`, or any production-touching script.
- Never run destructive DB ops against anything but the local supabase stack. `supabase db reset --linked` is forbidden. Local-only `cd app && npm run db:reset` is fine.
- Never commit ad-hoc seed scripts, screenshots, or log dumps.
- Don't skip the dedup step. Duplicate issues are noise.
- Don't file issues without screenshot + log evidence. Bare-text reports are insufficient.
- Don't bundle multiple bugs into one issue. One bug = one issue, even if you find five in one flow.
- Don't file issues for: things explicitly marked TODO/FIXME in code (those are known), or pre-existing console warnings that fire before you interact (note them in `flow_tests.md` instead).
- If `npm run db:up` or `npm run dev:sim` (both from `app/`) fails outright, file one infrastructure issue and stop.
