import { getAccessToken, refresh } from '@/lib/auth-client';

// Data API base URL (EXPO_PUBLIC_API_URL), matching auth-client.ts and
// ws-client.ts. The generated client emits absolute paths (`/api/...`,
// `/auth/...`), so the base is the bare API origin with no prefix. Defaults to
// localhost for local dev.
const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

async function doFetch(target: string, options: RequestInit, token: string | null) {
  return fetch(target, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

export async function pearFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const target = url.startsWith('http') ? url : `${API_BASE}${url}`;

  let res = await doFetch(target, options, getAccessToken());

  // On a 401, the access token is likely expired. Refresh once (single-flight)
  // and retry. If refresh fails, the auth client has cleared tokens → logged
  // out, and we fall through to the !ok error below.
  if (res.status === 401) {
    const fresh = await refresh();
    if (fresh) {
      res = await doFetch(target, options, fresh);
    }
  }

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
