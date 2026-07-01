import { getAccessToken, refresh } from '@/lib/auth-client';

// Data API base URL stays on Supabase Edge Functions for now — the cutover to
// the new backend is Phase 7. Phase 4A only changes WHERE the token comes from
// (our self-hosted auth client) and adds refresh-on-401 retry.
const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL;
if (!SUPABASE_URL) {
  throw new Error('EXPO_PUBLIC_SUPABASE_URL is not set');
}
const API_BASE = `${SUPABASE_URL}/functions/v1`;

async function doFetch(target: string, options: RequestInit, token: string | null) {
  return fetch(target, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'x-region': 'us-west-2',
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
