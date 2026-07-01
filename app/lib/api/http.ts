import { supabase } from '@/lib/supabase';

const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL;
if (!SUPABASE_URL) {
  throw new Error('EXPO_PUBLIC_SUPABASE_URL is not set');
}
const API_BASE = `${SUPABASE_URL}/functions/v1`;

export async function pearFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const target = url.startsWith('http') ? url : `${API_BASE}${url}`;

  const { data: sessionData } = await supabase.auth.getSession();
  const token = sessionData.session?.access_token;

  const res = await fetch(target, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'x-region': 'us-west-2',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
