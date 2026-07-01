// Auth client. Talks to the backend `/auth/*` endpoints over the shared
// cookie-bearing fetch. The session is a server-side cookie (HttpOnly, set by
// the backend on login). The client holds no token state: it just calls the
// endpoints with credentials included, and the cookie rides every request
// automatically. `restoreSession()` on launch is just a `me()` against the
// already-stored cookie.

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
// it back on every authenticated call. Throws on !ok with a readable message.
async function authFetch<T>(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const { method = 'POST', body } = options;
  const res = await fetch(`${API_URL}${path}`, {
    method,
    credentials: 'include',
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

// The authenticated user behind the current cookie, or throws if the cookie is
// missing/expired (the backend returns 401/403).
export async function me(): Promise<AuthUser> {
  const { user } = await authFetch<{ user: AuthUser }>('/auth/me', { method: 'GET' });
  return user;
}

// Restore a session on app launch: the cookie (if any) is already in the store,
// so this is just `me()`. Returns the current user, or null if not logged in.
export async function restoreSession(): Promise<AuthUser | null> {
  try {
    return await me();
  } catch {
    return null;
  }
}

// Clear the server-side session and the cookie. Best effort — the caller clears
// local state regardless.
export async function logout(): Promise<void> {
  await authFetch<void>('/auth/logout', { method: 'POST' }).catch(() => undefined);
}
