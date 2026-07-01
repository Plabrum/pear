import { queryClient } from '@/lib/queryClient';
import { authMeQueryKey } from '@/lib/auth-session';
import { ApiError } from '@/lib/api/errors';

// Re-export the error surface so existing `@/lib/api/http` import sites keep
// working; the definitions live in the leaf `errors.ts` to avoid require cycles.
export { ApiError, isApiError } from '@/lib/api/errors';
export type { ApiErrorKind } from '@/lib/api/errors';

// Data API base URL (EXPO_PUBLIC_API_URL), matching auth-client.ts and
// ws-client.ts. The generated client emits absolute paths (`/api/...`,
// `/auth/...`), so the base is the bare API origin with no prefix. Defaults to
// localhost for local dev.
const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

// Shared mutator for the generated client. Auth is a server-side cookie session:
// `credentials:'include'` sends the session cookie on every request and lets the
// server set it via Set-Cookie. No Authorization header, no token state, no
// refresh. Throws ApiError on failure; returns the parsed body directly.
export async function pearFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const target = url.startsWith('http') ? url : `${API_BASE}${url}`;
  const method = options.method ?? 'GET';

  let res: Response;
  try {
    res = await fetch(target, {
      ...options,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers ?? {}),
      },
    });
  } catch {
    // fetch rejects (TypeError) when the request never reaches the server:
    // offline, server down, DNS failure, connection refused/timed out.
    throw new ApiError(
      `Could not reach the server (${method} ${url})`,
      'network'
    );
  }

  const bodyText = [204, 205, 304].includes(res.status) ? null : await res.text();
  const contentType = res.headers.get('content-type') ?? '';
  const data: unknown =
    bodyText && contentType.includes('application/json') ? JSON.parse(bodyText) : bodyText;

  if (!res.ok) {
    // 401 = the server-side session is gone (expired, or Redis cleared on a
    // backend restart) while the client still thinks it's logged in. Invalidate
    // the session query directly — it refetches → null → the gate redirects to
    // login. No bridge/handler indirection; queryClient is a singleton.
    if (res.status === 401) {
      queryClient.invalidateQueries({ queryKey: authMeQueryKey });
    }
    throw new ApiError(
      `API ${method} ${url} failed: ${res.status} ${bodyText ?? ''}`,
      'http',
      res.status,
      userFacingDetail(data)
    );
  }

  return data as T;
}

// Pull a safe-to-display message out of an error body, but ONLY when the backend
// explicitly flagged it `user_facing` (see backend `UserFacingError`). Any other
// `detail` may be a developer string or a stack trace, so it's ignored here and
// the UI shows generic copy instead.
function userFacingDetail(data: unknown): string | undefined {
  if (typeof data !== 'object' || data === null) return undefined;
  const body = data as { detail?: unknown; user_facing?: unknown };
  if (body.user_facing === true && typeof body.detail === 'string') return body.detail;
  return undefined;
}

export default pearFetch;
