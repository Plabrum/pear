# Pear — AI Assistant Guide

## What This App Is

Pear (package `pear`, slug `wingmate`) is an iOS dating app. Two roles:

- **Dater** — browses profiles, swipes, chats with matches.
- **Winger** — a trusted friend who swipes on behalf of a dater.

Core flows: Auth → Onboarding → Discover → Matches → Messaging → Wingpeople.

---

## Tech Stack

| Layer          | Choice                                                                                                                                     |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Framework      | React Native 0.81 + Expo SDK 54 (new arch enabled)                                                                                         |
| Navigation     | expo-router v6 (file-based, typed routes)                                                                                                  |
| Backend        | **Self-hosted Litestar** (Python) + SQLAlchemy 2.0 async + Alembic + SAQ, on a single EC2 box via docker-compose (`api`/`worker`/`postgres:17`/`redis`/`caddy`). Own Postgres with **app-managed RLS** · S3 (media) · Litestar Channels (realtime) · direct APNs (push). |
| Styling        | NativeWind v5 preview + Tailwind v4 via `react-native-css`                                                                                 |
| Data fetching  | TanStack React Query v5 (`useSuspenseQuery` throughout)                                                                                    |
| Forms          | react-hook-form v7                                                                                                                         |
| Toasts         | sonner-native (`toast.error()` for all user-facing errors)                                                                                 |
| Animations     | react-native-reanimated v4                                                                                                                 |
| Build/deploy   | App: Xcode Cloud (build/sign/submit) + self-hosted OTA via GitHub Actions. Backend: GitHub Actions → ECR image → SSM deploy to the box (`.github/workflows/build-test-deploy.yml`). |
| API layer      | `backend/app/domain/<feature>` (Litestar) emits OpenAPI natively; Orval generates read hooks into `app/lib/api/generated/`; writes go through the typed **actions client** (`app/lib/api/actions.ts`). |

---

## Directory Structure

The repo is a monorepo with a root `Justfile`. Three workspaces:

- **`app/`** — the Expo app (this is where the mobile project lives; cwd for all `npm`/`expo` commands).
- **`backend/`** — the Litestar (Python) API + worker.
- **`infra/`** — Terraform for the single-EC2 deploy.

```
wingmate/
├── Justfile                    # Root task runner (just --list) — app-*, backend, db-*, tf-* recipes
├── app/                        # Expo app (cwd for npm/expo)
│   ├── app/                    # expo-router routes (the routes dir)
│   │   ├── _layout.tsx         # Root layout — providers, auth gate, Toaster
│   │   ├── invite.tsx          # Deep-link handler
│   │   ├── (auth)/             # login.tsx, sms.tsx, apple.tsx
│   │   ├── (onboarding)/index.tsx  # Onboarding orchestrator
│   │   ├── (tabs)/             # Dater tab shell (discover, matches, messages/, profile/)
│   │   └── (winger-tabs)/      # Winger tab shell (activity, friends/[id])
│   ├── components/             # onboarding/, profile/, ui/ (shared primitives)
│   ├── context/auth.tsx        # AuthProvider, useSession(), useAuth()
│   ├── lib/
│   │   ├── tw.tsx              # Styled primitives — ALWAYS import from here
│   │   ├── cn.ts              # clsx + tailwind-merge
│   │   ├── auth-client.ts      # Self-hosted auth: SecureStore refresh + in-mem access + refresh-on-401
│   │   ├── ws-client.ts        # Litestar Channels websocket (realtime)
│   │   ├── forms/index.tsx     # Button, TextInput, form primitives
│   │   └── api/
│   │       ├── http.ts         # pearFetch — sends session cookie (credentials:'include'), throws on !ok
│   │       ├── actions.ts      # Typed write client → POST /api/actions/{group}[/{id}]
│   │       └── generated/      # Orval read hooks (committed)
│   ├── hooks/ assets/ constants/  # constants/theme.ts = hex escape-hatch values
│   ├── scripts/                # dev/sim, etc.
│   ├── certs/                  # OTA code-signing public cert (updates-signing.pem) — must be
│   │                           # regenerated (see ios/) whenever the Terraform-managed signing
│   │                           # key rotates, not just copied once
│   ├── ios/                    # Committed native project (Xcode Cloud builds this directly,
│   │                           # does NOT run `expo prebuild`) — build output, not hand-edited;
│   │                           # regenerate via `expo prebuild -p ios` after any app.config.js /
│   │                           # certs/ change and commit the diff. Drift guarded by
│   │                           # .github/workflows/ios-drift-check.yml + a pre-commit hook +
│   │                           # ios/ci_scripts/ci_post_clone.sh (the last one is the real gate —
│   │                           # it aborts the Xcode Cloud build itself on drift).
│   ├── package.json  app.config.js  tsconfig.json  metro.config.js
│   ├── openapi.json            # Litestar-emitted OpenAPI spec (orval input, committed)
│   ├── orval.config.ts
│   └── global.css              # Tailwind v4 @theme tokens (source of truth)
├── backend/                    # Litestar API + worker (Python, uv)
│   ├── app/{config,factory,index}.py
│   ├── app/domain/<feature>/{models,enums,schemas,routes,actions,queries,state_machine}.py
│   ├── app/platform/{auth,actions,state_machine,base,queue,media,realtime}/  # cross-cutting
│   ├── alembic/                # migrations — the schema WRITE source of truth
│   ├── tests/                  # pytest (just test)
│   └── Dockerfile  docker-compose.dev.yml  pyproject.toml  scripts/{start,start-worker}.sh
├── infra/                      # Terraform (single-EC2; ECS path dormant) — see infra/README.md
├── .github/workflows/          # build-test-deploy (backend/** + infra/**)
└── CLAUDE.md
```

---

## Existing API Domains

All endpoints live under `backend/app/domain/<feature>/` (Litestar). Mounted under
`/api` in `backend/app/factory.py`; `/auth/*` and `/ws` stay at the root.

| Domain            | Owns                                              |
| ----------------- | ------------------------------------------------- |
| `contacts`        | Wingperson relationships (invite, accept, remove) |
| `decisions`       | Swipe likes/passes and winger suggestions         |
| `discover`        | Dater swipe feed + winger pool                    |
| `likes_you`       | Who liked the current dater                       |
| `matches`         | Mutual match list + detail                        |
| `messages`        | Chat message list + send                          |
| `photos`          | Photo upload, approval, delete                    |
| `profiles`        | Own profile read + edit                           |
| `prompts`         | Prompt templates, dater prompts, responses        |
| `wing_pool`       | Pool of profiles for a winger to swipe            |
| `winger_activity` | Feed of winger actions for the dater              |
| `winger_tabs`     | Winger-tab navigation data                        |
| `reports`         | Report/block a profile                            |

Cross-cutting platform code (auth, actions framework, state machine, RLS, queue,
media, realtime) lives under `backend/app/platform/`, not in a domain.

---

## How to Add a New Feature

The backend is **Litestar** with a read/write split: **reads** are GET routes
(Orval-generated hooks), **writes** are registered **actions** gated by a state
machine. A new domain lives under `backend/app/domain/<feature>/`:

1. **Model + enums** — SQLAlchemy model in `models.py`, `TextEnum` (StrEnum) members in
   `enums.py`. Then `just db-migrate "<message>"` (Alembic autogenerate). If the table
   needs RLS, reach for the reusable mixins in `rls_mixins.py` first: subclass
   `UserScopedMixin` (owner-only access; override the owner column with
   `class T(BaseDBModel, UserScopedMixin, user_id_column="...")`) for plain user-scoped
   tables, or `WingpersonScopedMixin` (owner OR active wingperson; `owner_column="..."`)
   for tables a dater and their active winger both touch. The mixin registers its
   `is_system_mode()`-escaped policy automatically — no `rls_policies.py` entry needed.
   Only hand-write a bespoke policy in `rls_policies.py` when the access shape genuinely
   diverges (public select, relational EXISTS joins, suggester/approval rules, etc.).
   Either way the table is enabled + FORCE RLS and the `pear_app` grants come
   automatically. `just db-upgrade` to apply locally.
2. **`schemas.py`** — `msgspec.Struct` request/response shapes. Derive literals from the
   domain enums.
3. **`routes.py`** — reads only. Use `CRUDConfig`/`make_crud_controller` for standard
   list/detail, or explicit `@get` handlers for bespoke shapes. Build a `<feature>_router`.
4. **`actions.py`** — all writes. Define an action group via `action_group_factory(...)`,
   then `@<feature>_actions` each `BaseTopLevelAction` / `BaseObjectAction`. Gate every
   state-changing action: implement `is_available` (narrow to the valid current state)
   and set `target_state` — go **through the state machine**
   (`deps.state_machine_service.transition(...)`); **never assign the status column
   directly**. The `discover_and_import(["actions.py", ...])` boot scan registers them.
5. **Register** the `<feature>_router` in the `/api` parent `Router` in
   `backend/app/factory.py`, and add the group's `ActionGroupType` member in
   `backend/app/platform/actions/enums.py`.
6. **Export OpenAPI + codegen the client:** regenerate `app/openapi.json` from the
   Litestar app, then `cd app && npm run api:gen` (Orval) to refresh
   `app/lib/api/generated/`.
7. **Screen reads** — import the generated hook `useGetApi<Feature>Suspense()` from
   `@/lib/api/generated/<tag>/<tag>.ts`. Destructure `data` directly.
8. **Screen writes** — call the typed action client in `app/lib/api/actions.ts`
   (`POST /api/actions/{group}[/{object_id}]`). Wire with `useMutation` +
   `invalidateQueries`.
9. **Tests** — add `backend/tests/test_<feature>.py` (pytest; `just test`).
10. **Commit** the generated artifacts (`app/openapi.json`, `app/lib/api/generated/`) in
    the same commit as the source that produced them.

**RLS note.** The app connects to Postgres as the **non-superuser `pear_app`** role, so
`FORCE ROW LEVEL SECURITY` is the real authorization floor (no owner/superuser bypass).
The honored escape for trusted bootstrap/worker code is the `public.is_system_mode()`
GUC (`SET LOCAL app.is_system_mode = true`), **not** a privileged connection. Per-request
the actor is set via `SET LOCAL app.user_id`. Never assign state columns directly —
mutations flow through actions + the state machine.

**System mode is tasks-only.** A user request/action may only create/read/update what
the caller can reach **under their own RLS scope**. The trusted RLS bypass —
`SET LOCAL app.is_system_mode = true`, `_enter_system_mode`, the state machine's
`system_transition`, and `MediaService.resolve_urls_system` — is allowed **only** in the
worker/task layer (`app/platform/queue/**` and any `tasks.py`) and tests. It must **never**
appear in a request handler / action / domain query. CI enforces this two ways:
`semgrep/no-request-path-system-mode.yml` and `backend/scripts/check_conventions.py` both
fail (ERROR) on any of those four entry points outside the allowed locations. Need a
system-scoped write from a request? Enqueue a task — don't reach for the escape inline.

**Raw SQL & DB sessions are infra-only.** Raw statement execution (`.execute(text(...))`,
`.execute("...")`, `.exec_driver_sql(...)`) and DB engine/session creation
(`create_async_engine`, `async_sessionmaker`, `sessionmaker`) live **only** in the
reviewed infra/task layer (engine/session wiring in `app/config.py` · `app/factory.py` ·
`app/utils/deps.py` · `app/platform/queue/**`; raw SQL additionally in
`app/platform/base/rls_*.py` and any `tasks.py`). Domains use the injected `transaction`
dependency and build queries with `select()`/`insert()`/`update()`. CI enforces this via
`semgrep/no-raw-sql.yml` and `backend/scripts/check_conventions.py`.

---

## Routing & Auth Gate

`RootNavigator` in `app/_layout.tsx` reads `session` from `useSession()`:

- No session → `/(auth)/login`
- No `chosen_name` → `/(onboarding)`
- Role = `winger` → `/(winger-tabs)`
- No `datingProfile` → `/(onboarding)`
- Otherwise → `/(tabs)/discover`

Two `useEffect`s allowed in `AuthenticatedNavigator`: deep-link invite check from AsyncStorage, and push token registration — both genuine external events.

---

## Auth Patterns

Auth is **self-hosted**. The backend exposes two `/auth/*` login methods:
**Apple Sign-In** verification and email **magic-link**. There is no phone/OTP path.

The session is a **server-side Redis session transported by an httpOnly cookie**
(Litestar `SessionAuth` + `ServerSideSessionConfig` + `RedisStore`, `samesite="lax"`) —
**not** a JWT or refresh token. Login (`/auth/apple`, `/auth/magic-link/verify`) sets the
session cookie via `Set-Cookie`; every subsequent request carries it. The only JWT in the
system is the *external* Apple identity token we verify in `clients/apple.py`.

On the client, `app/lib/auth-client.ts` is a thin cookie-bearing fetch
(`credentials: 'include'`) — no token storage, no `Authorization` header, no
refresh-on-401. It exposes `signInWithApple()`, `requestMagicLink(email)`,
`verifyMagicLink(token)`, `me()`, `restoreSession()`, `logout()`. The hook shapes are:

```ts
const { session, loading } = useSession(); // routing layer — session may be null
const { userId, session, signOut } = useAuth(); // authenticated screens — throws if no session
```

---

## Query Patterns

**Reads** go through Orval-generated `useGetApi*Suspense` hooks. `lib/api/http.ts`
returns the parsed body directly — no `{ data, status }` wrapper, no status checks at
callsites; it sends the session cookie (`credentials: 'include'`) and throws on a non-2xx.

**Writes** go through the typed action client `lib/api/actions.ts`, which hits
`POST /api/actions/{group}[/{object_id}]` with a tagged-union body
(`{ action, data }`) and returns `ActionExecutionResponse`
(`{ message, invalidate_queries, action_result, created_id }`). Wire with `useMutation`
+ `invalidateQueries`.

Realtime is the Litestar Channels websocket (`lib/ws-client.ts`, connects to
`EXPO_PUBLIC_API_URL`'s `/ws` with its own `?token=`). Don't add ad-hoc client
selects — add a Litestar GET route (read) or an action (write).

---

## Codegen

The schema source of truth is **Alembic** (`backend/alembic/`); the API contract is
the **Litestar-emitted OpenAPI** (`app/openapi.json`), which Orval turns into typed
read hooks. The chain after a backend change:

```bash
# 1. schema: SQLAlchemy model → migration
just db-migrate "<message>"   # alembic revision --autogenerate
just db-upgrade               # alembic upgrade head (local)

# 2. contract: export the Litestar OpenAPI → app/openapi.json, then Orval
cd app && npm run api:gen     # orval ← app/openapi.json → app/lib/api/generated/
```

Run after: new/changed Litestar routes or schemas, and new actions. Idempotent.

**Hard constraints:**

- Schema writes go through **Alembic migrations only** — never hand-edit the DB.
- Generated artifacts (`app/openapi.json`, `app/lib/api/generated/`) belong in the same
  commit as the source change.

---

## Backend Architecture (Litestar)

`backend/` is a single Litestar app (`app/factory.py` builds it; `app/index.py` is the
ASGI entry). Runs as `api` + `worker` (SAQ) containers; co-located `postgres`/`redis`/`caddy`.

- **Auth.** Litestar `SessionAuth` reads the httpOnly session cookie, loads the session
  from Redis, and rehydrates the actor via `retrieve_user_handler`.
  `/auth/*` (Apple/magic-link) and `/ws` live at the root; everything else under `/api`.
- **Per-request DB + RLS.** Each request runs in a transaction on a connection opened as
  the **non-superuser `pear_app`** role, with `SET LOCAL app.user_id` (the actor). Because
  `pear_app` owns nothing, **FORCE RLS** is the genuine authorization floor — handler-side
  filters are for correctness/perf, not security. Trusted bootstrap/worker code uses the
  `public.is_system_mode()` escape (`SET LOCAL app.is_system_mode = true`), not a
  privileged connection.
- **Reads vs writes.** Reads are GET routes; **writes are registered actions** executed
  through `POST /api/actions/...`, gated by the per-domain state machine — never assign a
  status column directly.
- **Side effects** (push via direct **APNs**, email via **SES**, realtime broadcasts) fire
  from inside actions / queued SAQ tasks. No standalone functions.
- **Config & secrets.** `backend/app/config.py` reads env (`ENV`, `ASYNC_DATABASE_URL`
  vs `ADMIN_DB_URL`, `DB_APP_USER`/`DB_APP_PASSWORD`, `SECRET_KEY` (session signing),
  `SESSION_MAX_AGE_SECONDS`, `REDIS_URL`, `APPLE_CLIENT_ID`, `MAGIC_LINK_TTL_SECONDS`,
  `APNS_*`, `S3_*`, `SES_*`). In prod these come from Secrets Manager
  (merged into `/opt/pear/.env` by `deploy.sh`); local/testing select `Local*` clients
  (push/email/S3 no-op or log).

---

## Data Model Summary

Full schema in `data_model.md`. Key tables:

| Table              | Purpose                                                      |
| ------------------ | ------------------------------------------------------------ |
| `profiles`         | Base user (auth + name + phone + gender + role)              |
| `dating_profiles`  | Dater config (bio, city, preferences, dating_status)         |
| `profile_photos`   | Photos with approval flow; `suggester_id` null = self-upload |
| `prompt_templates` | Predefined questions                                         |
| `profile_prompts`  | A dater's chosen prompt + answer                             |
| `prompt_responses` | Wingperson/match comments on a prompt (needs approval)       |
| `contacts`         | Dater ↔ Winger relationship                                  |
| `decisions`        | Like/pass/suggestion; mutual 'approved' triggers a Match     |
| `matches`          | Mutual match record                                          |
| `messages`         | Chat messages per match                                      |

Key enums: `role`: `dater|winger` · `dating_status`: `open|break|winging` · `wingperson_status`: `invited|active|removed` · `decision`: `approved|declined|null`

---

## Shared UI Components (`components/ui/`)

| Component                                | Key props                                   |
| ---------------------------------------- | ------------------------------------------- |
| `Pill`                                   | `label`                                     |
| `WingStack`                              | `initials: string[]`, `size?`               |
| `PhotoRect`                              | `uri`, `ratio?`, `blur?`                    |
| `FaceAvatar`                             | `initials`, `bg`, `size?`                   |
| `LargeHeader`                            | `title`, `right?`                           |
| `NavHeader`                              | `back`, `onBack`, `title`, `sub?`, `right?` |
| `TextTabBar`                             | `tabs`, `active`, `setActive`               |
| `DateInput`                              | platform-split date picker                  |
| `ScreenSuspense` / `ScreenErrorBoundary` | screen wrappers                             |

**Button** lives in `lib/forms/` — `import { Button } from '@/lib/forms'`. Variants: `default`, `outline`, `ghost`, `destructive`. Never hardcode a filled CTA manually.

---

## Styling (NativeWind v5 + Tailwind v4)

- **Always** import styled primitives from `@/lib/tw`: `View`, `Text`, `Pressable`, `ScrollView`, `TextInput`, `SafeAreaView`, `AnimatedView`.
- Never use `StyleSheet.create` — use `className`.
- `style` prop only for: `borderCurve`, dynamic/animated values, SVG props.
- Never use function-style `style` on `Pressable` (NativeWind bug #1105 — children don't render). Use `active:` pseudo-class.
- `cn()` from `@/lib/cn` for conditional classes.
- Design tokens in `global.css` under `@theme` — never add raw hex to `constants/theme.ts`.

**Modal color caveat:** CSS variables aren't injected in Modal's native layer. Use `ModalView` from `@/lib/tw` with a `backgroundColor` style prop (not className) for colors inside Modals.

### Design Tokens

**Surfaces:** `bg-background` (#F5F1E8) · `bg-surface` (#FBF8F1) · `bg-surface-muted` (#EDE6D6)

**Text:** `text-foreground`/`text-fg` · `text-foreground-muted`/`text-fg-muted` · `text-foreground-subtle`/`text-fg-subtle`

**Brand:** `text-primary`/`bg-primary` (leaf green) · `text-primary-soft`/`bg-primary-soft`

**Accent:** `text-accent`/`bg-accent` · `bg-accent-muted`

**Borders:** `border-border` · `border-border-subtle`

**Status:** `text-destructive` · `text-green` (presence)

**Fonts:** `font-serif` (DMSerifDisplay, display headers) · `font-sans` (Geist, body)

**Sizes:** `text-11` through `text-30` · **Radii:** `radius-4/9/13/14/16/18/21/22/26`

**Escape hatch** (icon `color=`, animated values): `import { colors } from '@/constants/theme'` — `colors.primary` `colors.primarySoft` `colors.ink` `colors.inkMid` `colors.inkDim` `colors.divider` `colors.green` `colors.white`.

---

## Coding Preferences

- **Composition:** Orchestrators decide what to render; logic lives close to where it's used.
- **Control flow:** `switch` on discriminated unions. Explicit `return` on every branch.
- **No `useEffect`:** Move async work into transition handlers. Exceptions: the auth-provider mount effect (restore session on launch + handle the magic-link deep link), push token registration, AsyncStorage deep-link check (mount-only, genuine external events).
- **Error propagation:** No try/catch across callback boundaries. Return errors as values. User-facing errors via `toast.error()`.
- **Forms:** react-hook-form everywhere — `Controller`, `handleSubmit`, `isSubmitting`, `isValid`, `mode: 'onChange'`.
- **Queries:** Transforms belong in the query function. Unwrapping boilerplate belongs in the query wrapper, not callsites. No magic string cache keys.
- `async/await` over `.then()`.

---

## Development Workflows

The repo is a monorepo. All app commands run from `app/` — either via the root `Justfile`
(`just --list` to see recipes) or directly with `cd app && npm run …`.

All recipes are in the root `Justfile` (`just --list`). The common ones:

```bash
# Everything at once (backend api + worker + Expo sim)
just dev

# Backend (Litestar, Python/uv — from repo root)
just db-start         # local postgres + redis (docker compose)
just db-upgrade       # alembic upgrade head
just db-migrate "msg" # alembic autogenerate a new revision
just dev-backend      # litestar api, hot-reload, :8000
just dev-worker       # SAQ worker
just test             # pytest
just lint-backend     # ruff check --fix + format
just check-backend    # basedpyright

# App (Expo — these cd into app/)
cd app && npm run dev:sim        # iOS Simulator
cd app && npm run web            # Expo web
cd app && npm run api:gen        # Orval ← app/openapi.json (after a backend contract change)
cd app && npx tsc --noEmit && npm run lint

# Build & deploy the app (Xcode Cloud + self-hosted OTA — separate from the backend pipeline)
cd app && npm run export:ota     # expo export -p ios — JS bundle for the OTA publish job (ota.yml)
cd app && npm run build:device   # opens ios/Pear.xcworkspace in Xcode — pick your device, hit Run
                                  # (cloud-managed signing means no local certs/profiles to script;
                                  # this builds the same committed ios/ Xcode Cloud builds from)
# Native archive/sign/submit (TestFlight/App Store) runs in Xcode Cloud, triggered on `v*` tags —
# no local EAS build/submit step.
```

**Env.** `backend/.env.local` (or repo-root `.env.local`) carries the backend secrets
(`DB_*`, `SECRET_KEY`, `REDIS_URL`, `APPLE_*`, `APNS_*`, `S3_*`, `SES_*`); local dev falls back
to safe defaults (port 5432, `Local*` clients). The app needs
`EXPO_PUBLIC_API_URL=https://api.<domain>` (or `http://localhost:8000` locally) — it is
the only backend coordinate the client needs.

**Terraform (`infra/`).** All infra changes are committed to the repo and applied via
CI/CD (`.github/workflows/build-test-deploy.yml` / the infra workflow) — never run
`terraform apply` (or `import`/`destroy`) against the real backend from a local machine
or an agent session, even with valid AWS credentials on hand. `terraform plan` is fine
for review. Land the `.tf` changes in a PR and let the pipeline apply them.

---

## Image Handling

- `expo-image-picker` — select from camera roll
- `expo-image-manipulator` — resize to max 1200px, quality 0.8, JPEG
- `expo-image` — display (not RN Image)

---

## Build Configuration

- **Bundle ID:** `com.plabrum.pear`
- **Version source:** `package.json` · **Runtime version:** fingerprint · **New Architecture:** enabled
- No EAS — native build/sign/submit is Xcode Cloud (triggered on `v*` tags), building the
  committed `app/ios/` project directly. No `eas.json`, no EAS profiles.

---

## TypeScript

- Strict mode. Path alias `@/*` → `./` (relative to `app/`).
- The typed API surface is the Orval-generated `app/lib/api/generated/` (reads) +
  `app/lib/api/actions.ts` (writes), both derived from `app/openapi.json`. Treat generated
  files as build output — never hand-edit; regenerate via `npm run api:gen`.
