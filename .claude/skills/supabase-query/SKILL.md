---
name: supabase-query
description: >
  Write Supabase + TanStack Query v5 useSuspenseQuery data-fetching code for this Expo/React Native app.
  Use whenever the user asks to add a query, hook, or data fetch — or when reviewing existing fetching
  code for correctness. Enforces the project's specific patterns: two-layer structure (plain query
  function + useSuspenseQuery hook), function-ref cache keys, error throwing inside queryFn,
  simple transforms in queryFn (not components), { data, error } unwrapping in the query function,
  and type exports. Trigger on phrases like "add a query for", "fetch X from the DB", "hook for
  loading", "useSuspenseQuery", "how do I get X from Supabase", or whenever someone asks to add
  data fetching to a screen.
---

# Supabase + TanStack Query v5 Pattern Guide

This app uses a consistent two-layer structure for all data fetching. Follow it exactly.

## Layer 1 — Plain query function

A plain `async` function (or one that returns the raw Supabase builder promise) lives in the right `queries/*.ts` file. Two valid styles:

**Style A — returns raw Supabase builder** (for simple, single-table queries):

```ts
export function getProfilePhotos(datingProfileId: string) {
  return supabase
    .from('profile_photos')
    .select('id, storage_url, display_order, approved_at, suggester_id')
    .eq('dating_profile_id', datingProfileId)
    .order('display_order', { ascending: true });
}
```

The queryFn then unwraps `{ data, error }` and throws.

**Style B — async function that throws** (for multi-step or combined queries):

```ts
export async function getWingpeopleWithCounts(daterId: string) {
  const [wpResult, invResult] = await Promise.all([
    getMyWingpeople(daterId),
    getIncomingInvitations(daterId),
  ]);
  if (wpResult.error) throw new Error(wpResult.error.message);
  if (invResult.error) throw new Error(invResult.error.message);
  return { wingpeople: wpResult.data ?? [], invitations: invResult.data ?? [] };
}
```

The queryFn then calls it directly with no further error handling.

**Don't mix the two** — if the plain function already throws, the queryFn shouldn't re-wrap in `{ data, error }`, and vice versa.

## Layer 2 — useSuspenseQuery hook

```ts
import { useSuspenseQuery } from '@tanstack/react-query';

// Wrapping Style A (raw builder):
export function useProfilePhotos(datingProfileId: string) {
  return useSuspenseQuery({
    queryKey: [getProfilePhotos, datingProfileId],
    queryFn: async () => {
      const { data, error } = await getProfilePhotos(datingProfileId);
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 2 * 60_000,
  });
}

// Wrapping Style B (async function that throws):
export function useWingpeopleData(userId: string) {
  return useSuspenseQuery({
    queryKey: [getWingpeopleWithCounts, userId],
    queryFn: () => getWingpeopleWithCounts(userId),
    staleTime: 2 * 60_000,
  });
}
```

The component just calls `const { data } = useProfilePhotos(datingProfileId)` — no unwrapping, no error state, no loading state.

---

## Critical rules (with reasons)

### 1. Function reference as cache key

```ts
// ✅ correct
queryKey: [getProfilePhotos, datingProfileId];

// ❌ wrong — magic strings drift silently when the function is renamed
queryKey: ['profile-photos', datingProfileId];
```

The function reference ties the key to the actual function, so renames are caught by TypeScript.

### 2. Error handling: one layer, not two

Pick the right style for layer 1, then the queryFn handles it correctly — don't do both:

```ts
// ❌ wrong — double handling: function throws AND queryFn also checks error
async function getThings() {
  const { data, error } = await supabase.from('things').select('*');
  if (error) throw error; // throws here
  return data ?? [];
}

function useThings() {
  return useSuspenseQuery({
    queryFn: async () => {
      const { data, error } = await getThings(); // error is never set — getThings() throws
      if (error) throw error; // ← redundant
      return data;
    },
  });
}

// ✅ correct for style A: raw builder, unwrap in queryFn
function getThings() {
  return supabase.from('things').select('*');
}
function useThings() {
  return useSuspenseQuery({
    queryFn: async () => {
      const { data, error } = await getThings();
      if (error) throw error;
      return data ?? [];
    },
  });
}

// ✅ correct for style B: async throws, queryFn just calls it
async function getThings() {
  const { data, error } = await supabase.from('things').select('*');
  if (error) throw error;
  return data ?? [];
}
function useThings() {
  return useSuspenseQuery({
    queryFn: () => getThings(),
  });
}
```

### 3. Simple transforms belong in queryFn — complex logic does not

Transforms like sort, shuffle, filter, and null-coalescing are fine in queryFn:

```ts
queryFn: async () => {
  const { data, error } = await getDiscoverPool(userId);
  if (error) throw error;
  return (data ?? []).sort(() => Math.random() - 0.5);  // ✅ simple sort
},
```

But **complex business logic** (grouping across entities, counting per-entity, multi-step aggregation) should NOT live in queryFn. Instead:

- **Option A — two separate queries**: one hook for the list, one for the counts; combine at the call site
- **Option B — a plain helper function** separate from the query, called wherever it's needed

```ts
// ❌ wrong — complex aggregation crammed into queryFn makes it untestable and hard to read
queryFn: async () => {
  const { data } = await supabase.from('decisions').select('*').eq('suggested_by', wingerId);
  const map = new Map<string, number>();
  for (const row of data ?? []) {
    map.set(row.actor_id, (map.get(row.actor_id) ?? 0) + 1);
  }
  return [...map.entries()].map(([id, count]) => ({ id, count }));
},

// ✅ option A — two focused queries
export function useDaterList(wingerId) { /* simple select */ }
export function usePendingCountsForWinger(wingerId) { /* count query */ }

// ✅ option B — helper function
export function groupByDater(rows: Decision[]): DaterCount[] {
  const map = new Map<string, number>();
  for (const row of rows) { map.set(row.actor_id, (map.get(row.actor_id) ?? 0) + 1); }
  return [...map.entries()].map(([id, count]) => ({ id, count }));
}
```

### 4. Parallel fetches with Promise.all (Style B only)

When one async function needs several related pieces of data:

```ts
export async function getMatchSheetData(userId: string, otherUserId: string) {
  const [noteResult, promptResult] = await Promise.all([
    getWingNoteForMatch(userId, otherUserId),
    getMatchPrompts(otherUserId),
  ]);
  if (noteResult.error) throw new Error(noteResult.error.message);
  if (promptResult.error) throw new Error(promptResult.error.message);
  return { wingNote: noteResult.data, prompts: promptResult.data };
}
```

### 5. staleTime — choose based on how volatile the data is

| Data type                        | staleTime                   |
| -------------------------------- | --------------------------- |
| Realtime / swipe pool            | `0`                         |
| Conversation list, unread counts | `30_000`                    |
| Matches                          | `60_000`                    |
| Profiles, wingpeople             | `2 * 60_000` – `5 * 60_000` |
| Static (prompt templates)        | `Infinity`                  |

---

## Type exports

Export the inferred type of query results so callers don't have to repeat the derivation:

```ts
// For style A (returns raw builder):
export type ProfilePhoto = NonNullable<
  Awaited<ReturnType<typeof getProfilePhotos>>['data']
>[number];

// For style B (returns clean data array):
export type Notification = NonNullable<Awaited<ReturnType<typeof getNotifications>>>[number];

// For combined result:
export type MatchSheetData = Awaited<ReturnType<typeof getMatchSheetData>>;
```

---

## Where does new code go?

| What you're fetching         | File                                                               |
| ---------------------------- | ------------------------------------------------------------------ |
| Own profile / dating profile | `queries/profiles.ts`                                              |
| Discover / wing pool         | `queries/discover.ts`                                              |
| Matches                      | `queries/matches.ts`                                               |
| Messages / conversations     | `queries/messages.ts`                                              |
| Wingpeople / contacts        | `queries/contacts.ts`                                              |
| Photos                       | `queries/photos.ts`                                                |
| Prompts                      | `queries/prompts.ts`                                               |
| New domain                   | Create `queries/<domain>.ts` and re-export from `queries/index.ts` |

Always note which file the code belongs in with a comment at the top. Always re-export new functions/hooks from `queries/index.ts`.

---

## Complete example — end-to-end

**Task:** Add a hook to fetch how many unread messages a user has in a specific match.

```ts
// queries/messages.ts  (add to existing file)

/** Count of unread messages in a given match for the viewer. Style A. */
export function getUnreadCountForMatch(matchId: string, viewerId: string) {
  return supabase
    .from('messages')
    .select('id', { count: 'exact', head: true })
    .eq('match_id', matchId)
    .neq('sender_id', viewerId)
    .eq('is_read', false);
}

export function useUnreadCountForMatch(matchId: string, viewerId: string) {
  return useSuspenseQuery({
    queryKey: [getUnreadCountForMatch, matchId, viewerId],
    queryFn: async () => {
      const { count, error } = await getUnreadCountForMatch(matchId, viewerId);
      if (error) throw error;
      return count ?? 0;
    },
    staleTime: 30_000,
  });
}
```

**Usage in component:**

```tsx
// Must be wrapped in <ScreenSuspense> and <ScreenErrorBoundary>
function MessagesBadge({ matchId, userId }: { matchId: string; userId: string }) {
  const { data: count } = useUnreadCountForMatch(matchId, userId);
  if (count === 0) return null;
  return <Text className="text-purple font-bold">{count}</Text>;
}
```

---

## Anti-patterns checklist

Before finishing, verify:

- [ ] No `useQuery` — always `useSuspenseQuery`
- [ ] No string-only cache keys — function reference first
- [ ] No double error handling (if layer-1 throws, queryFn doesn't also unwrap)
- [ ] No complex business logic aggregation in queryFn — use two queries or a helper
- [ ] Simple transforms (sort/filter/shuffle) are fine in queryFn
- [ ] New hook re-exported from `queries/index.ts`
- [ ] Target file noted in a comment (`// queries/messages.ts`)
- [ ] `staleTime` appropriate for data volatility
