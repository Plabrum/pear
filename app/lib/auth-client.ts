// Auth client. Talks to the backend `/auth/*` endpoints over the shared
// cookie-bearing fetch. The session is a server-side cookie (HttpOnly, set by
// the backend on login). The client holds no token state: it just calls the
// endpoints with credentials included, and the cookie rides every request
// automatically. The session query (lib/auth-session.ts) calls `me()` to read
// the current user; it bootstraps on mount instead of a manual restore.

import { ApiError } from '@/lib/api/errors';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

export type AuthUser = {
  id: string;
  role: 'dater' | 'winger' | null;
  chosenName?: string | null;
};

type AuthError = { error: string };

function isAuthError(value: unknown): value is AuthError {
  return typeof value === 'object' && value !== null && 'error' in value;
}

// Bare fetch against the auth backend. Always sends the session cookie
// (credentials:'include'); the server sets it via Set-Cookie on login and reads
// it back on every authenticated call. Throws `ApiError` on failure — mirroring
// pearFetch — so callers (the session queryFn) can tell an unreachable backend
// ('network') apart from a 401 ('http', status 401).
async function authFetch<T>(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const { method = 'POST', body } = options;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    // fetch rejects when the request never reaches the server: offline, server
    // down, DNS failure, connection refused/timed out.
    throw new ApiError(`Could not reach the server (${method} ${path})`, 'network');
  }

  const text = [204, 205, 304].includes(res.status) ? null : await res.text();
  const contentType = res.headers.get('content-type') ?? '';
  const data: unknown =
    text && contentType.includes('application/json') ? JSON.parse(text) : text;

  if (!res.ok) {
    const message = isAuthError(data) ? data.error : (text ?? `Request failed (${res.status})`);
    throw new ApiError(message, 'http', res.status);
  }

  return data as T;
}

// --- Login methods ---
// Each sets the session cookie server-side (Set-Cookie) and returns the user.

export async function signInWithApple(
  identityToken: string,
  fullName?: string
): Promise<AuthUser> {
  return authFetch<AuthUser>('/auth/apple', {
    body: { identityToken, ...(fullName ? { fullName } : {}) },
  });
}

export async function requestMagicLink(email: string): Promise<void> {
  await authFetch<void>('/auth/magic-link/request', { body: { email } });
}

export async function verifyMagicLink(token: string): Promise<AuthUser> {
  return authFetch<AuthUser>('/auth/magic-link/verify', { body: { token } });
}

// --- Session lifecycle ---

// The authenticated user behind the current cookie plus whether they've finished
// dating-profile onboarding. Throws `ApiError` (status 401) if the cookie is
// missing/expired; the session queryFn maps that 401 to `null`.
export async function me(): Promise<{ user: AuthUser; hasDatingProfile: boolean }> {
  const { user, hasDatingProfile } = await authFetch<{
    user: AuthUser;
    hasDatingProfile: boolean;
  }>('/auth/me', { method: 'GET' });
  return { user, hasDatingProfile };
}

// Clear the server-side session and the cookie. Best effort — the caller clears
// local state regardless.
export async function logout(): Promise<void> {
  await authFetch<void>('/auth/logout', { method: 'POST' }).catch(() => undefined);
}
