// Leaf module — no imports, so it can be safely shared by http.ts, queryClient.ts,
// auth-client.ts and auth-session.ts without forming a require cycle.

// Thrown by the fetch layer on any failed request. `kind` lets the error
// boundary / query layer tell an unreachable backend ("you're offline") apart
// from a genuine bad response ("this request is broken"):
//   - 'network'  → fetch itself rejected (offline, server down, DNS, timeout).
//                  `status` is undefined; retrying may succeed.
//   - 'http'     → the server responded with a non-2xx. `status` is the code;
//                  4xx are not worth retrying, 5xx might be transient.
export type ApiErrorKind = 'network' | 'http';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  // A backend-authored, safe-to-display sentence. Set ONLY when the response was
  // flagged `user_facing` (see backend `UserFacingError`). When present it's the
  // preferred toast text; otherwise the UI falls back to generic/action-specific
  // copy and `message` (the verbose debug string) stays logs-only.
  readonly userMessage?: string;

  constructor(message: string, kind: ApiErrorKind, status?: number, userMessage?: string) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.userMessage = userMessage;
  }

  // Unreachable backend — distinct from a server-side 4xx/5xx response.
  get isNetworkError(): boolean {
    return this.kind === 'network';
  }

  // The session is dead (expired, or Redis cleared on a backend restart). Routing
  // treats this as a redirect-to-login handoff, not a screen error.
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}
