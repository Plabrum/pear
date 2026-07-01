import React, { createContext, useContext, useEffect, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import * as SplashScreen from 'expo-splash-screen';
import { supabase } from '@/lib/supabase';

type AuthContextValue = {
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<{ error: Error | null }>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

// Plain functions — no React state needed
export async function sendOTP(phone: string) {
  const { error } = await supabase.auth.signInWithOtp({ phone });
  return { error };
}

export async function verifyOTP(phone: string, token: string) {
  const { error } = await supabase.auth.verifyOtp({ phone, token, type: 'sms' });
  return { error };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if ((event === 'INITIAL_SESSION' || event === 'SIGNED_OUT') && __DEV__ && !session) {
        supabase.auth
          .signInWithPassword({ email: 'dev@local.test', password: 'devpassword' })
          .then(({ error }) => {
            if (error) {
              console.error('[dev] auto sign-in failed:', error.message);
              setLoading(false);
              SplashScreen.hideAsync();
            }
          });
        return;
      }
      setSession(session);
      setLoading(false);
      SplashScreen.hideAsync();
    });

    return () => subscription.unsubscribe();
  }, []);

  async function signOut() {
    const { error } = await supabase.auth.signOut();
    return { error };
  }

  return (
    <AuthContext.Provider value={{ session, loading, signOut }}>{children}</AuthContext.Provider>
  );
}

// For the routing layer — session may be null
export function useSession() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useSession must be used within AuthProvider');
  return ctx;
}

// For authenticated screens — throws if called without a session
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
