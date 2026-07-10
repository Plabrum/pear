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
| Framework      | Bare React Native 0.85 (new arch enabled) — zero Expo: no `expo` package, no `EXPO_*` env vars, no `babel-preset-expo`/`eslint-config-expo`, nothing Expo-branded anywhere in the dependency graph or build pipeline. `ios/` is built directly by Xcode Cloud, not `expo prebuild`. The Xcode project itself (`project.pbxproj`, `.xcworkspace`) is XcodeGen-generated from `app/ios/project.yml` and not committed — edit `project.yml`, not the generated project, and run `xcodegen generate && pod install` (or `npm run dev:sim`, which does this automatically) to pick up changes. |
| Navigation     | `@react-navigation` v7 (native-stack + bottom-tabs) — `App.tsx`/`navigation/RootNavigator.tsx`, not file-based routing                     |
| Backend        | **Self-hosted Litestar** (Python) + SQLAlchemy 2.0 async + Alembic + SAQ, on a single EC2 box via docker-compose (`api`/`worker`/`postgres:17`/`redis`/`caddy`). Own Postgres with **app-managed RLS** · S3 (media) · Litestar Channels (realtime) · direct APNs (push, hand-rolled `PearNotificationsModule.swift`). |
| Styling        | NativeWind v4 + Tailwind v3 (`nativewind/metro` on `@react-native/metro-config`)                                   |
| Data fetching  | TanStack React Query v5 (`useSuspenseQuery` throughout)                                                                                    |
| Forms          | react-hook-form v7                                                                                                                         |
| Toasts         | sonner-native (`toast.error()` for all user-facing errors)                                                                                 |
| Animations     | react-native-reanimated v4                                                                                                                 |
| Build/deploy   | App: Xcode Cloud (build/sign/submit) + self-hosted OTA via GitHub Actions. Backend: GitHub Actions → ECR image → SSM deploy to the box (`.github/workflows/build-test-deploy.yml`). |
| API layer      | `backend/app/domain/<feature>` (Litestar) emits OpenAPI natively; Orval generates read hooks into `app/lib/api/generated/`; writes go through the typed **actions client** (`app/lib/api/actions.ts`). |

---

## Directory Structure

The repo is a monorepo with a root `Justfile`. Three workspaces:

- **`app/`** — the bare React Native app (this is where the mobile project lives; cwd for all `npm` CLI commands).
- **`backend/`** — the Litestar (Python) API + worker.
- **`infra/`** — Terraform for the single-EC2 deploy.

```
wingmate/
├── Justfile                    # Root task runner (just --list) — app-*, backend, db-*, tf-* recipes
├── app/                        # Bare React Native app (cwd for npm CLI)
│   ├── App.tsx                 # Root component — providers, fonts-free (static UIAppFonts
│   │                           # linking), StatusBar. No Linking/invite-handoff code here —
│   │                           # the magic-link deep-link listener lives in context/auth.tsx,
│   │                           # the pending-invite handoff in navigation/RootNavigator.tsx.
│   ├── index.js                # AppRegistry.registerComponent entry point
│   ├── app.json                # `{"name": "main", ...}` — AppRegistry name, must stay "main"
│   │                           # (ios/Pear/AppDelegate.swift hardcodes it)
│   ├── navigation/             # @react-navigation tree: RootNavigator.tsx (4-way auth-gate
│   │                           # conditional render), types.ts (RootStackParamList),
│   │                           # pendingIntents.ts, plus one file per nested Tab/Stack
│   │                           # navigator (WingerTabsNavigator.tsx, DaterTabsNavigator.tsx,
│   │                           # FriendsStackNavigator.tsx, MessagesStackNavigator.tsx,
│   │                           # ProfileStackNavigator.tsx)
│   ├── features/               # Screen files, one flat dir per feature (not a routes dir —
│   │                           # no file-based routing; replaced the old app/(group)/ tree):
│   │   ├── root/               # invite.tsx, magic-link.tsx, settings.tsx — the always-mounted
│   │   │                       # root-level screens
│   │   ├── auth/                # login.tsx, EmailSheet.tsx (no phone/OTP, no separate Apple screen)
│   │   ├── onboarding/          # index.tsx orchestrator, chrome.tsx, RoleStep.tsx, ProfileSetup.tsx, steps/
│   │   ├── discover/, matches/, messages/  # Dater tab shell screens
│   │   ├── profile/             # index.tsx, edit.tsx, edit/, tabs
│   │   ├── wingpeople/          # index.tsx, contribute.tsx, wingswipe.tsx, ContactsPicker.tsx,
│   │   │                       # InviteWingpersonSheet.tsx, WingerActivityFeed.tsx
│   │   ├── winger/              # activity.tsx, me.tsx — Winger tab shell
│   │   └── friends/             # index.tsx, [id]/
│   ├── components/             # Flat dir of ~30 shared primitives (not onboarding/profile/ui/
│   │                           # subfolders) — see Shared UI Components below. Two subdirs:
│   │                           # actions/ (form components for actions) and icons/.
│   ├── context/auth.tsx        # AuthProvider, useSession(), useAuth(), useAuthActions()
│   ├── lib/
│   │   ├── tw.tsx              # Styled primitives — ALWAYS import from here
│   │   ├── cn.ts              # clsx + tailwind-merge
│   │   ├── auth-client.ts      # Self-hosted auth: cookie-bearing fetch (credentials:'include')
│   │   ├── auth-session.ts     # getAuthGateStatus() — source of truth for the routing auth gate
│   │   ├── ws-client.ts        # Litestar Channels websocket (realtime)
│   │   ├── forms/               # fields.tsx (Controller-based field kit), typed-form.tsx (createTypedForm)
│   │   ├── actions/             # registry.tsx, types.ts — action-executor plumbing
│   │   └── api/
│   │       ├── http.ts         # pearFetch — sends session cookie (credentials:'include'), throws on !ok
│   │       ├── actions.ts      # Typed write client → POST /api/actions/{group}[/{id}]
│   │       ├── errors.ts, error-toast.ts
│   │       └── generated/      # Orval read hooks (committed)
│   ├── hooks/                   # use-swipe-deck.ts, use-messages.ts, use-presence.ts, use-typing.ts,
│   │                           # use-upload-profile-photo.ts, actions/ (use-action-executor.ts, etc.)
│   ├── assets/ constants/       # constants/theme.ts = hex escape-hatch values, constants/enums.ts
│   ├── scripts/                # dev/sim, etc.
│   ├── ios/                    # Native project for Xcode Cloud — no `expo prebuild` step,
│   │                           # zero Expo (the off-Expo migration's native-ownership
│   │                           # cutover removed the ios-drift-check workflow/hook entirely).
│   │                           # `Pear.xcodeproj`/`Pear.xcworkspace` are XcodeGen-generated
│   │                           # from `project.yml` (not committed) — edit `project.yml`,
│   │                           # then `xcodegen generate && pod install`. Everything else
│   │                           # (Swift/ObjC sources, entitlements/Info.plist content in
│   │                           # `project.yml`, `Pear/OTA/updates-signing.pem` — the OTA
│   │                           # code-signing public cert for the custom Swift OTA client's
│   │                           # signature verification, regenerated only via CI/CD when the
│   │                           # Terraform-managed signing key rotates) is hand-maintained.
│   ├── package.json  tsconfig.json  metro.config.js
│   ├── openapi.json            # Litestar-emitted OpenAPI spec (orval input, committed)
│   ├── orval.config.ts
│   └── global.css              # Tailwind v3 tokens as plain :root custom properties (source of truth)
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
| `dating_profiles` | Dater config (bio, city, preferences, dating_status) |
| `users`           | User-level account data                           |

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

`RootNavigator` (`navigation/RootNavigator.tsx`) reads `session` from `useSession()`, computes one of four statuses via `getAuthGateStatus()` (`lib/auth-session.ts`), and conditionally renders one of four top-level `<RootStack.Screen>`s — not file-based routing:

- No session → `Login`
- No `chosenName`, or no dating profile and role isn't `winger` → `Onboarding`
- Role = `winger` → `WingerTabs`
- Otherwise → `DaterTabs`

`Invite`, `MagicLink`, and `Settings` are always-mounted root-level screens alongside the gated ones. Cross-navigator jumps need React Navigation's nested-object `navigate()` syntax (e.g. `navigate('DaterTabs', { screen: 'Profile', params: { screen: 'WingpeopleList' } })`) — plain `navigate('ScreenName')` only bubbles up to an ancestor, never down into an unrelated sibling subtree.

Two `useEffect`s allowed in `RootNavigator`: the pending-intent handoff (winger-invite deep link / onboarding destination, both recorded before their target navigator is mounted) and push-token registration — both genuine external events.

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
`verifyMagicLink(token)`, `me()`, `logout()` — screens consume the first three via
`useAuthActions()` in `context/auth.tsx`, not directly. Session restore is a plain
`useQuery` (no `restoreSession()` function). The hook shapes are:

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
`APP_PUBLIC_API_URL`'s `/ws` with its own `?token=`). Don't add ad-hoc client
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

## Shared UI Components (`components/`)

| Component                                | Key props                                   |
| ---------------------------------------- | ------------------------------------------- |
| `Pill`                                   | `label?`, `children?`, `tone?`, `size?`     |
| `WingStack`                              | `items: WingStackItem[]`, `size?`, `max?`, `label?` |
| `PhotoRect`                              | `uri`, `ratio?`, `blur?`, `style?`          |
| `FaceAvatar`                             | `name`, `size?`, `photoUri?`, `ring?`       |
| `LargeHeader`                            | `title`, `right?`                           |
| `NavHeader`                              | `back`, `onBack`, `title`, `sub?`, `right?` |
| `LargeNavHeader`                         | `back`, `onBack`, `title`, `right?` — large-serif chrome for full-screen sub-pages (settings, wingpeople, profile edit, contribute) |
| `EmptyCard`                              | `children` — dashed-border empty-state panel |
| `TextTabBar`                             | `tabs`, `active`, `setActive`, `badges?`    |
| `DateInput`/`DateInput.native`           | platform-split date picker (web `<input type=date>` vs `@react-native-community/datetimepicker`) |
| `ScreenSuspense` / `ScreenErrorBoundary` | screen wrappers                             |
| `Card`, `Dialog`, `Sheet`, `FullSheet`, `ForwardSheet` | modal/sheet shells — see [Form/modal kit] pattern; prefer these over hand-rolled `Modal` |
| `NoteModal`, `PagedCarousel`, `AvatarPicker`, `GradientBlock`, `PulseSpinner`, `SectionLabel`, `FieldLabel`, `tabBar`, `icon-symbol`, `PearMark`, `Splash` | other shared primitives — check here before writing new markup |

**Button** lives in `components/Button.tsx` — `import { Button } from '@/components/Button'`. Variants: `primary`, `secondary`, `accent`, `ghost`, `danger`. Sizes: `sm`, `md`, `lg`. Props: `block`, `icon`, `disabled`, `loading`. Never hardcode a filled CTA manually.

---

## Styling (NativeWind v4 + Tailwind v3)

- **Always** import styled primitives from `@/lib/tw`: `View`, `Text`, `Pressable`, `ScrollView`, `TextInput`, `SafeAreaView`, `AnimatedView`.
- Never use `StyleSheet.create` — use `className`.
- `style` prop only for: `borderCurve`, dynamic/animated values, SVG props.
- Never use function-style `style` on `Pressable` (NativeWind bug #1105 — children don't render). Use `active:` pseudo-class.
- `cn()` from `@/lib/cn` for conditional classes.
- Design tokens in `global.css` under `@theme` — never add raw hex to `constants/theme.ts`.
- Never hard-code raw hex/`rgba(...)` literals in component files either — always go through a `className` color utility or `colors.*` from `@/constants/theme`. If a needed color doesn't have a token yet, add it to `theme.ts`/`global.css` rather than inlining it.

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

**Escape hatch** (icon `color=`, animated values): `import { colors } from '@/constants/theme'` — `colors.primary` `colors.primarySoft` `colors.ink` `colors.inkMid` `colors.inkDim` `colors.divider` `colors.green` `colors.white`, plus ~40 more (state/overlay/decorative tints) — check `theme.ts` for the full set. Note `theme.ts`'s hex values are hand-kept approximations of `global.css`'s CSS-var tokens, not always byte-identical — `theme.ts` says as much in its own comment.

---

## Coding Preferences

- **Composition:** Orchestrators decide what to render; logic lives close to where it's used.
- **Control flow:** `switch` on discriminated unions. Explicit `return` on every branch.
- **No `useEffect`:** Move async work into transition handlers. Exceptions (mount-only, genuine external events): the auth-provider mount effect for the magic-link deep-link listener (`context/auth.tsx`), push-token registration (`navigation/RootNavigator.tsx`), and the pending-intent handoff (`navigation/RootNavigator.tsx`/`pendingIntents.ts`, in-memory module state — no AsyncStorage in this app).
- **Error propagation:** No try/catch across callback boundaries. Return errors as values. User-facing errors via `toast.error()`.
- **Forms:** react-hook-form everywhere — `Controller`, `handleSubmit`, `isSubmitting`, `isValid`, `mode: 'onChange'`.
- **Queries:** Transforms belong in the query function. Unwrapping boilerplate belongs in the query wrapper, not callsites. No magic string cache keys.
- `async/await` over `.then()`.
- **Reuse the shared kit:** don't hand-roll a back-chevron header, tag pill, or filled CTA button — use `NavHeader`/`LargeNavHeader`, `Pill`, or `Button` from `components/` before writing new `Pressable`/`TouchableOpacity` markup.

---

## Development Workflows

The repo is a monorepo. All app commands run from `app/` — either via the root `Justfile`
(`just --list` to see recipes) or directly with `cd app && npm run …`.

All recipes are in the root `Justfile` (`just --list`). The common ones:

```bash
# Everything at once (backend api + worker + iOS sim)
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

# App (these cd into app/)
cd app && npm run dev:sim        # iOS Simulator
cd app && npm run api:gen        # Orval ← app/openapi.json (after a backend contract change)
cd app && npx tsc --noEmit && npm run lint

# Build & deploy the app (Xcode Cloud + self-hosted OTA — separate from the backend pipeline)
cd app && npm run export:ota     # scripts/export-ota-bundle.js — JS bundle for the OTA publish job (ota.yml)
cd app && npm run build:device   # opens ios/Pear.xcworkspace in Xcode — pick your device, hit Run
                                  # (requires an `xcodegen generate && pod install` first if the
                                  # workspace hasn't been generated yet, e.g. via `npm run dev:sim`;
                                  # cloud-managed signing means no local certs/profiles to script —
                                  # this builds the same project Xcode Cloud builds from)
# Native archive/sign/submit (TestFlight/App Store) runs in Xcode Cloud, triggered on `v*` tags —
# no local EAS build/submit step.
```

**Env.** `backend/.env.local` (or repo-root `.env.local`) carries the backend secrets
(`DB_*`, `SECRET_KEY`, `REDIS_URL`, `APPLE_*`, `APNS_*`, `S3_*`, `SES_*`); local dev falls back
to safe defaults (port 5432, `Local*` clients). The app needs
`APP_PUBLIC_API_URL=https://api.<domain>` (or `http://localhost:8000` locally) — it is
the only backend coordinate the client needs.

**Terraform (`infra/`).** All infra changes are committed to the repo and applied via
CI/CD (`.github/workflows/build-test-deploy.yml` / the infra workflow) — never run
`terraform apply` (or `import`/`destroy`) against the real backend from a local machine
or an agent session, even with valid AWS credentials on hand. `terraform plan` is fine
for review. Land the `.tf` changes in a PR and let the pipeline apply them.

---

## Image Handling

- `react-native-image-crop-picker` — select from camera roll (`lib/photos.ts`'s `pickAndResizePhoto`)
- `@bam.tech/react-native-image-resizer` — resize to max 1200px width, JPEG compress
- RN core `<Image>` + hand-rolled `components/CrossfadeImage.tsx` — display, with the
  expo-image `transition` crossfade reimplemented as two stacked `Image`s + `Animated.timing`

---

## Build Configuration

- **Bundle ID:** `com.plabrum.pear`
- **Version source:** `package.json` for the JS side; `MARKETING_VERSION`/`CURRENT_PROJECT_VERSION`
  in `app/ios/project.yml` for `CFBundleShortVersionString`/`CFBundleVersion` (bump both on
  release — the generated `Info.plist` only ever reflects `project.yml`, never edit it directly).
  **Runtime version:** fingerprint · **New Architecture:** enabled
- No EAS — native build/sign/submit is Xcode Cloud (triggered on `v*` tags), building the
  `app/ios/` project (XcodeGen-generated from the committed `project.yml`) directly. No
  `eas.json`, no EAS profiles.

---

## TypeScript

- Strict mode. Path alias `@/*` → `./` (relative to `app/`).
- The typed API surface is the Orval-generated `app/lib/api/generated/` (reads) +
  `app/lib/api/actions.ts` (writes), both derived from `app/openapi.json`. Treat generated
  files as build output — never hand-edit; regenerate via `npm run api:gen`.
