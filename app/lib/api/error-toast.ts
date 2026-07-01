import { toast } from 'sonner-native';
import { isApiError } from '@/lib/api/errors';

// The single way to surface a thrown error to the user. Two audiences, two
// channels — and they must never cross:
//
//   • developers → the full error (status, URL, body, stack). Logged here only;
//     `ApiError.message` deliberately carries the verbose debug string. Wire
//     Sentry/crash reporting in `logError` and every callsite gets it for free.
//   • users      → a short, safe sentence. NEVER the raw backend body. That's
//     what `resolveErrorMessage` returns and the toast shows.
//
// Callsites pass the action-specific copy as `fallback` ("Couldn't save bio.");
// this helper layers the cross-cutting concerns (offline detection, logging,
// generic catch-all) on top so no screen has to re-implement them.

const GENERIC = 'Something went wrong. Please try again.';
const OFFLINE = "Can't reach the server. Check your connection and try again.";

/**
 * Map any thrown value to a user-safe sentence. Resolution ladder:
 *   1. unreachable backend          → offline copy (overrides the fallback —
 *                                      "couldn't save" is misleading when the
 *                                      request never left the device)
 *   2. backend `user_facing` message → a deliberate, server-authored sentence
 *                                      (e.g. "You've already invited this
 *                                      person") — more specific than the fallback
 *   3. caller-supplied `fallback`   → the action-specific message
 *   4. generic catch-all
 *
 * A non-2xx body is otherwise ignored: it may be a stack trace or an internal
 * detail. Backend text surfaces ONLY when flagged user-facing (see `ApiError` /
 * backend `UserFacingError`).
 */
export function resolveErrorMessage(err: unknown, fallback?: string): string {
  if (isApiError(err)) {
    if (err.isNetworkError) return OFFLINE;
    if (err.userMessage) return err.userMessage;
  }
  return fallback ?? GENERIC;
}

/** Log the full error for debugging. Single chokepoint for Sentry/crash wiring. */
function logError(err: unknown): void {
  console.error(err);
}

/**
 * Surface an error to the user: log the real error, then toast a safe message.
 * Use this in every catch / onError that shows an error toast.
 */
export function toastError(err: unknown, fallback?: string): void {
  logError(err);
  toast.error(resolveErrorMessage(err, fallback));
}
