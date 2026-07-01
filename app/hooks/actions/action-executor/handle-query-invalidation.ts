import type { QueryClient } from '@tanstack/react-query';

import type { ActionExecutionResponse } from '@/lib/actions/types';

/**
 * Invalidate the queries a backend action's `invalidate_queries` paths map to.
 *
 * Ported 1:1 from sloopquest. The backend emits kebab URL-path tokens
 * (`/wingpeople`, `/dating-profiles/swipe`, `/conversations`, …) that match the
 * Orval query keys, so a substring match on each query's first (path) segment
 * flushes every list/detail derived from it — no app-specific tag→key map needed.
 */
export function handleQueryInvalidation(
  queryClient: QueryClient,
  response: ActionExecutionResponse,
  onInvalidate?: (queryClient: QueryClient, backendQueryKeys: string[]) => void
): void {
  const backendQueryKeys = response.invalidate_queries ?? [];

  backendQueryKeys.forEach((key) => {
    queryClient.invalidateQueries({
      predicate: (query) =>
        Array.isArray(query.queryKey) &&
        typeof query.queryKey[0] === 'string' &&
        (query.queryKey[0] === key || query.queryKey[0].includes(key)),
    });
  });

  onInvalidate?.(queryClient, backendQueryKeys);
}
