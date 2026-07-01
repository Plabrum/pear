import { QueryClient } from '@tanstack/react-query';
import { isApiError } from '@/lib/api/errors';

// Retry transient failures (unreachable backend, 5xx) a few times with
// exponential backoff, but fail fast on a genuine 4xx — retrying a bad request
// or an unauthorized call never helps and just delays the error boundary.
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 3) return false;
  if (isApiError(error)) {
    if (error.kind === 'network') return true;
    return error.status !== undefined && error.status >= 500;
  }
  return false;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: shouldRetry,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
});
