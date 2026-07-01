import { useEffect } from 'react';
import { Redirect } from 'expo-router';
import { useSession } from '@/context/auth';

// In-memory handoff for the winger-invite deep link. The deep link
// (`pear://invite`) opens the app; if the user still needs to log in, we
// remember the intent here and the root gate (app/_layout.tsx) consumes it
// after auth to land them on the wingpeople screen. This lives for the process
// lifetime, which spans the launch -> login flow of a single invite tap — no
// AsyncStorage required.
let pendingWingerInvite = false;

export function peekPendingWingerInvite(): boolean {
  return pendingWingerInvite;
}

export function clearPendingWingerInvite(): void {
  pendingWingerInvite = false;
}

export default function InviteRedirect() {
  const { session, loading } = useSession();

  // Record the invite intent as a side effect of landing on this deep-link
  // screen unauthenticated — never during render (that would mutate module
  // state mid-render). Handling a deep link is a genuine external event, so a
  // mount/identity effect is the sanctioned place for it (see CLAUDE.md).
  useEffect(() => {
    if (!loading && !session) pendingWingerInvite = true;
  }, [loading, session]);

  if (loading) return null;

  // Already authenticated — deep-link straight to wingpeople.
  if (session) return <Redirect href="/(tabs)/profile/wingpeople" />;

  // Not authenticated — route to login; the effect above remembers the intent
  // and the root gate picks it up once the session lands.
  return <Redirect href="/(auth)/login" />;
}
