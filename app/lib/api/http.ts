// Data API base URL (EXPO_PUBLIC_API_URL), matching auth-client.ts and
// ws-client.ts. The generated client emits absolute paths (`/api/...`,
// `/auth/...`), so the base is the bare API origin with no prefix. Defaults to
// localhost for local dev.
const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

// Shared mutator for the generated client. Auth is a server-side cookie session:
// `credentials:'include'` sends the session cookie on every request and lets the
// server set it via Set-Cookie. No Authorization header, no token state, no
// refresh. Throws on !ok; returns the parsed body directly.
export async function pearFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const target = url.startsWith('http') ? url : `${API_BASE}${url}`;

  const res = await fetch(target, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  });

  const bodyText = [204, 205, 304].includes(res.status) ? null : await res.text();
  const contentType = res.headers.get('content-type') ?? '';
  const data: unknown =
    bodyText && contentType.includes('application/json') ? JSON.parse(bodyText) : bodyText;

  if (!res.ok) {
    throw new Error(
      `API ${options.method ?? 'GET'} ${url} failed: ${res.status} ${bodyText ?? ''}`
    );
  }

  return data as T;
}

export default pearFetch;
