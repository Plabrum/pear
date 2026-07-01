import * as SecureStore from 'expo-secure-store';

// Self-hosted auth client (Phase 4A).
//
// Talks to the new backend at EXPO_PUBLIC_API_URL (the /auth/* endpoints).
// - refreshToken: persisted in SecureStore (rotating, opaque).
// - accessToken: held in memory only (short-lived ES256 JWT).
//
// Does NOT use supabase-js. Storage + realtime keep their own supabase client
// until Phase 6; only the auth layer moves here.

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

const REFRESH_TOKEN_KEY = 'pear.auth.refreshToken';

export type AuthUser = {
  id: string;
  role: 'dater' | 'winger' | null;
  chosenName?: string | null;
};

export type AuthTokens = {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
};

type RefreshResponse = {
  accessToken: string;
  refreshToken: string;
};

// In-memory access token. Never persisted.
let accessToken: string | null = null;

// Single-flight guard: concurrent 401s share one refresh() call.
let refreshInFlight: Promise<string | null> | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

async function getStoredRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
}

async function persistRefreshToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
}

async function clearTokens(): Promise<void> {
  accessToken = null;
  await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
}

type AuthError = { error: string };

function isAuthError(value: unknown): value is AuthError {
  return typeof value === 'object' && value !== null && 'error' in value;
}

// Bare fetch against the auth backend. Throws on !ok with a readable message.
// Used only for the unauthenticated /auth/* calls — no Bearer attached here.
async function authFetch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  const text = [204, 205, 304].includes(res.status) ? null : await res.text();
  const contentType = res.headers.get('content-type') ?? '';
  const data: unknown =
    text && contentType.includes('application/json') ? JSON.parse(text) : text;

  if (!res.ok) {
    const message = isAuthError(data) ? data.error : (text ?? `Request failed (${res.status})`);
    throw new Error(message);
  }

  return data as T;
}

// Adopt a fresh login/refresh result: persist refresh token + set access token.
async function adoptTokens(tokens: AuthTokens): Promise<AuthUser> {
  accessToken = tokens.accessToken;
  await persistRefreshToken(tokens.refreshToken);
  return tokens.user;
}

// --- Login methods ---

export async function otpStart(phone: string): Promise<void> {
  await authFetch<void>('/auth/otp/start', { phone });
}

export async function otpCheck(phone: string, code: string): Promise<AuthUser> {
  const tokens = await authFetch<AuthTokens>('/auth/otp/check', { phone, code });
  return adoptTokens(tokens);
}

export async function appleSignIn(identityToken: string, fullName?: string): Promise<AuthUser> {
  const tokens = await authFetch<AuthTokens>('/auth/apple', {
    identityToken,
    ...(fullName ? { fullName } : {}),
  });
  return adoptTokens(tokens);
}

export async function magicLinkRequest(email: string): Promise<void> {
  await authFetch<void>('/auth/magic-link/request', { email });
}

export async function magicLinkVerify(token: string): Promise<AuthUser> {
  const tokens = await authFetch<AuthTokens>('/auth/magic-link/verify', { token });
  return adoptTokens(tokens);
}

// --- Session lifecycle ---

// Rotates both tokens using the stored refresh token. Returns the new access
// token on success, or null if there is no refresh token / refresh failed
// (in which case tokens are cleared → logged out).
//
// Single-flight: concurrent callers (e.g. multiple 401s) await the same promise.
export function refresh(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;

  const run = async (): Promise<string | null> => {
    const stored = await getStoredRefreshToken();
    if (!stored) {
      await clearTokens();
      return null;
    }

    try {
      const tokens = await authFetch<RefreshResponse>('/auth/refresh', {
        refreshToken: stored,
      });
      accessToken = tokens.accessToken;
      await persistRefreshToken(tokens.refreshToken);
      return tokens.accessToken;
    } catch {
      await clearTokens();
      return null;
    }
  };

  refreshInFlight = run().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

// Restore a session on app launch from the stored refresh token.
// Returns the current user, or null if not logged in.
export async function restoreSession(): Promise<AuthUser | null> {
  const token = await refresh();
  if (!token) return null;
  return me();
}

export async function me(): Promise<AuthUser> {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed to load session (${res.status})`);
  }

  const { user } = (await res.json()) as { user: AuthUser };
  return user;
}

export async function logout(): Promise<void> {
  const stored = await getStoredRefreshToken();
  await clearTokens();
  if (stored) {
    // Best effort — local state is already cleared.
    await authFetch<void>('/auth/logout', { refreshToken: stored }).catch(() => undefined);
  }
}
