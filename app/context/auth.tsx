import React, { createContext, useContext, useEffect } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import { Linking } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import {
  signInWithApple as clientSignInWithApple,
  logout as clientLogout,
  requestMagicLink as clientRequestMagicLink,
  verifyMagicLink as clientVerifyMagicLink,
} from '@/lib/auth-client';
import { queryClient } from '@/lib/queryClient';
import { authMeQueryKey, sessionQueryOptions, type Session } from '@/lib/auth-session';
import Splash from '@/components/ui/Splash';
import ScreenErrorBoundary from '@/components/ui/ScreenErrorBoundary';

export type { Session };

type AuthResult = { error: Error | null };

type AuthContextValue = {
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<AuthResult>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // The session query is the single source of truth. `data === null` is the
  // normal unauthenticated state; a query `error` means the backend is
  // unreachable (a 401 resolves to null, not an error).
  const { data: session, isPending, error, refetch } = useQuery(sessionQueryOptions);

  // Hide the native splash once the session has settled (data or error), and
  // keep it up while pending. Effect because it pokes a native module.
  useEffect(() => {
    if (!isPending) SplashScreen.hideAsync();
  }, [isPending]);

  // Magic-link deep link — a genuine external event (inbound URL), so a
  // mount-only effect is the sanctioned exception. On a verified token we
  // invalidate the session query (refetches the full session incl.
  // hasDatingProfile) rather than setting state directly.
  useEffect(() => {
    async function handleMagicLink(url: string | null): Promise<void> {
      if (!url) return;
      const parsed = new URL(url);
      const hostname = parsed.hostname;
      if (hostname !== 'magic-link') return;
      const token = parsed.searchParams.get('token');
      if (typeof token !== 'string') return;
      try {
        await clientVerifyMagicLink(token);
        await queryClient.invalidateQueries({ queryKey: authMeQueryKey });
      } catch {
        // A bad/expired token leaves the session untouched — the gate keeps the
        // user on login.
      }
    }

    const subscription = Linking.addEventListener('url', ({ url }) => {
      handleMagicLink(url);
    });
    Linking.getInitialURL().then(handleMagicLink);

    return () => subscription.remove();
  }, []);

  async function signOut(): Promise<AuthResult> {
    try {
      await clientLogout();
      queryClient.setQueryData(authMeQueryKey, null);
      queryClient.clear();
      return { error: null };
    } catch (e) {
      queryClient.setQueryData(authMeQueryKey, null);
      queryClient.clear();
      return { error: e instanceof Error ? e : new Error('Failed to sign out') };
    }
  }

  // Bootstrapping: keep the branded splash up until the session settles.
  if (isPending) return <Splash />;

  // Unreachable backend — surface the offline/retry screen (issue #90). A 401
  // never lands here; it resolves to `null` (unauthenticated).
  if (error) {
    return (
      <ScreenErrorBoundary onRetry={() => refetch()}>
        <OfflineThrow error={error} />
      </ScreenErrorBoundary>
    );
  }

  return (
    <AuthContext.Provider value={{ session: session ?? null, loading: false, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

// Rethrows the session query's network error into the boundary so the offline
// state renders with the same UI every other screen uses.
function OfflineThrow({ error }: { error: unknown }): never {
  throw error;
}

// --- Login actions used by screens ---

export function useAuthActions() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthActions must be used within AuthProvider');

  return {
    async signInWithApple(identityToken: string, fullName?: string): Promise<AuthResult> {
      try {
        await clientSignInWithApple(identityToken, fullName);
        await queryClient.invalidateQueries({ queryKey: authMeQueryKey });
        return { error: null };
      } catch (e) {
        return { error: e instanceof Error ? e : new Error('Apple sign-in failed') };
      }
    },
    async requestMagicLink(email: string): Promise<AuthResult> {
      try {
        await clientRequestMagicLink(email);
        return { error: null };
      } catch (e) {
        return { error: e instanceof Error ? e : new Error('Failed to send magic link') };
      }
    },
    async verifyMagicLink(token: string): Promise<AuthResult> {
      try {
        await clientVerifyMagicLink(token);
        await queryClient.invalidateQueries({ queryKey: authMeQueryKey });
        return { error: null };
      } catch (e) {
        return { error: e instanceof Error ? e : new Error('Failed to verify magic link') };
      }
    },
  };
}

// For the routing layer — session may be null.
export function useSession() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useSession must be used within AuthProvider');
  return { session: ctx.session, loading: ctx.loading };
}

// For authenticated screens — throws if called without a session (should never
// fire under the gate).
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  if (!ctx.session) throw new Error('useAuth called outside authenticated context');
  return {
    userId: ctx.session.user.id,
    session: ctx.session,
    signOut: ctx.signOut,
  };
}
