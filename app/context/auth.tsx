import React, { createContext, useContext, useEffect, useState } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import * as Linking from 'expo-linking';
import {
  appleSignIn as clientAppleSignIn,
  getAccessToken,
  logout as clientLogout,
  magicLinkRequest as clientMagicLinkRequest,
  magicLinkVerify as clientMagicLinkVerify,
  otpCheck,
  otpStart,
  restoreSession,
  type AuthUser,
} from '@/lib/auth-client';

// Session shape consumed by the routing gate (app/_layout.tsx reads
// session.user.id) and screens. `user` carries the backend's AuthUser fields;
// `phone` stays optional for the onboarding default.
export type Session = {
  user: AuthUser & { phone?: string | null };
};

function toSession(user: AuthUser | null): Session | null {
  return user ? { user } : null;
}

type AuthResult = { error: Error | null };

type AuthContextValue = {
  session: Session | null;
  loading: boolean;
  setSession: (user: AuthUser | null) => void;
  signOut: () => Promise<AuthResult>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

// --- Start-OTP (plain function — no session commit, so no React state) ---
// Returns { error } rather than throwing across the callback boundary.
// The verify step that commits a session lives in useAuthActions().verifyOTP.

export async function sendOTP(phone: string): Promise<AuthResult> {
  try {
    await otpStart(phone);
    return { error: null };
  } catch (e) {
    return { error: e instanceof Error ? e : new Error('Failed to send code') };
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  function setSession(user: AuthUser | null) {
    setSessionState(toSession(user));
  }

  // Mount-only: hydrate from the stored refresh token + wire the magic-link
  // deep link. Both are genuine external events (app launch + inbound URL),
  // which fall under the allowed mount-only effect exception.
  useEffect(() => {
    let active = true;

    async function handleMagicLink(url: string | null): Promise<boolean> {
      if (!url) return false;
      const { hostname, queryParams } = Linking.parse(url);
      if (hostname !== 'magic-link') return false;
      const token = queryParams?.token;
      if (typeof token !== 'string') return false;
      try {
        const user = await clientMagicLinkVerify(token);
        if (active) setSession(user);
        return true;
      } catch {
        return false;
      }
    }

    async function bootstrap() {
      const initialUrl = await Linking.getInitialURL();
      const handledLink = await handleMagicLink(initialUrl);

      if (!handledLink) {
        const user = await restoreSession();
        if (active) setSession(user);
      }

      if (active) {
        setLoading(false);
        SplashScreen.hideAsync();
      }
    }

    const subscription = Linking.addEventListener('url', ({ url }) => {
      handleMagicLink(url);
    });

    bootstrap();

    return () => {
      active = false;
      subscription.remove();
    };
  }, []);

  async function signOut(): Promise<AuthResult> {
    try {
      await clientLogout();
      setSessionState(null);
      return { error: null };
    } catch (e) {
      setSessionState(null);
      return { error: e instanceof Error ? e : new Error('Failed to sign out') };
    }
  }

  return (
    <AuthContext.Provider value={{ session, loading, setSession, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

// --- Login actions used by screens (set the session via context) ---

export function useAuthActions() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthActions must be used within AuthProvider');
  const { setSession } = ctx;

  return {
    // Phone OTP verify that also commits the session.
    async verifyOTP(phone: string, code: string): Promise<AuthResult> {
      try {
        const user = await otpCheck(phone, code);
        setSession(user);
        return { error: null };
      } catch (e) {
        return { error: e instanceof Error ? e : new Error('Failed to verify code') };
      }
    },
    async signInWithApple(identityToken: string, fullName?: string): Promise<AuthResult> {
      try {
        const user = await clientAppleSignIn(identityToken, fullName);
        setSession(user);
        return { error: null };
      } catch (e) {
        return { error: e instanceof Error ? e : new Error('Apple sign-in failed') };
      }
    },
    async requestMagicLink(email: string): Promise<AuthResult> {
      try {
        await clientMagicLinkRequest(email);
        return { error: null };
      } catch (e) {
        return { error: e instanceof Error ? e : new Error('Failed to send magic link') };
      }
    },
    async verifyMagicLink(token: string): Promise<AuthResult> {
      try {
        const user = await clientMagicLinkVerify(token);
        setSession(user);
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

// For authenticated screens — throws if called without a session.
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

// Re-export the in-memory access token getter for any direct callers.
export { getAccessToken };
