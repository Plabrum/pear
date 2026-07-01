// The single source of truth for auth state. One React Query (`['auth','me']`)
// holds the session; nothing keeps auth in useState. The HTTP layer invalidates
// this query on any 401 (lib/api/http.ts), the AuthProvider branches on its
// state, and the routing gate redirects off `session`.

import { me, type AuthUser } from '@/lib/auth-client';
import { isApiError } from '@/lib/api/errors';

export const authMeQueryKey = ['auth', 'me'] as const;

// The resolved session. `null` (not an error) is the normal unauthenticated
// state; a thrown error means the backend was unreachable.
export type Session = {
  user: AuthUser;
  hasDatingProfile: boolean;
};

// Calls `me()`; returns the Session on success, `null` on a 401 (unauthenticated
// is a normal state, not an error), and rethrows network errors so they surface
// as a query error → offline/retry screen.
export async function fetchSession(): Promise<Session | null> {
  try {
    const { user, hasDatingProfile } = await me();
    return { user, hasDatingProfile };
  } catch (err) {
    if (isApiError(err) && err.status === 401) return null;
    throw err;
  }
}

// `staleTime: Infinity` — the session never refetches on its own; it's refreshed
// explicitly (login, logout, deep-link verify) or invalidated by a 401.
export const sessionQueryOptions = {
  queryKey: authMeQueryKey,
  queryFn: fetchSession,
  staleTime: Infinity,
} as const;

// The auth ladder. Every screen that needs to know "what does this session
// resolve to" — app/_layout.tsx's Stack.Protected guards, app/magic-link.tsx's
// post-verify redirect — switches on this single status instead of
// re-deriving onboarding/role booleans inline.
export type AuthGateStatus = 'unauthenticated' | 'onboarding' | 'winger' | 'dater';

export function getAuthGateStatus(session: Session | null): AuthGateStatus {
  if (!session) return 'unauthenticated';
  const needsOnboarding =
    !session.user.chosenName || (!session.hasDatingProfile && session.user.role !== 'winger');
  if (needsOnboarding) return 'onboarding';
  return session.user.role === 'winger' ? 'winger' : 'dater';
}
