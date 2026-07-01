import { useRef } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import type { SwipeProfile } from '@/lib/api/generated/model';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import { shortKey } from '@/lib/actions/types';

const PAGE_SIZE = 20;

export type LikeResult = 'match' | 'liked' | 'error';

export type PoolFetcher = (
  userId: string,
  pageSize: number,
  offset: number
) => Promise<SwipeProfile[]>;

type Params = {
  /** The swipe query's key — the optimistic deck mutates its cached array. */
  queryKey: QueryKey;
  /** The cached pool (from the parent's suspense query); the head is the current card. */
  pool: SwipeProfile[];
  fetchPool: PoolFetcher;
  userId: string | null;
};

/**
 * The swipe deck, driven entirely by the react-query cache. The current card is the
 * head of the cached pool; a swipe optimistically drops the head via setQueryData
 * (free optimism + rollback) and routes the decision through the action executor
 * (which records it + invalidates the side-effects — matches/decisions/etc., but NOT
 * the pool, so the deck isn't refetched mid-swipe). No hand-rolled index/pool state.
 */
export function useDiscover({ queryKey, pool, fetchPool, userId }: Params) {
  const queryClient = useQueryClient();
  const executor = useActionExecutor({ actionGroup: 'dating_profile_swipe_actions' });

  const swipingRef = useRef(false);
  const loadingMoreRef = useRef(false);
  const offsetRef = useRef(pool.length);

  const card = pool[0] ?? null;

  function removeTop() {
    queryClient.setQueryData<SwipeProfile[]>(queryKey, (old) => (old ?? []).slice(1));
  }

  async function loadMore() {
    if (!userId || loadingMoreRef.current) return;
    loadingMoreRef.current = true;
    const data = await fetchPool(userId, PAGE_SIZE, offsetRef.current);
    if (data.length > 0) {
      queryClient.setQueryData<SwipeProfile[]>(queryKey, (old) => [...(old ?? []), ...data]);
      offsetRef.current += data.length;
    }
    loadingMoreRef.current = false;
  }

  function actionFor(c: SwipeProfile, key: string) {
    return (c.actions ?? []).find((a) => shortKey(a.action) === key);
  }

  async function like(): Promise<LikeResult> {
    const c = pool[0];
    if (!c || swipingRef.current) return 'error';
    const action = actionFor(c, 'like');
    if (!action) return 'error';
    swipingRef.current = true;
    const snapshot = queryClient.getQueryData<SwipeProfile[]>(queryKey);
    removeTop();
    if (pool.length - 1 <= 3) loadMore();
    try {
      const res = await executor.executeAction(action, undefined, { objectId: c.profileId, silent: true });
      swipingRef.current = false;
      return res.created_id != null ? 'match' : 'liked';
    } catch {
      queryClient.setQueryData(queryKey, snapshot); // roll back the optimistic removal
      swipingRef.current = false;
      return 'error';
    }
  }

  async function pass(): Promise<void> {
    const c = pool[0];
    if (!c || swipingRef.current) return;
    const action = actionFor(c, 'pass');
    if (!action) return;
    swipingRef.current = true;
    const snapshot = queryClient.getQueryData<SwipeProfile[]>(queryKey);
    removeTop();
    if (pool.length - 1 <= 3) loadMore();
    try {
      await executor.executeAction(action, undefined, { objectId: c.profileId, silent: true });
    } catch {
      queryClient.setQueryData(queryKey, snapshot);
    }
    swipingRef.current = false;
  }

  async function report(reason: string): Promise<void> {
    const c = pool[0];
    if (!c) return;
    const action = actionFor(c, 'report');
    if (!action) return;
    const snapshot = queryClient.getQueryData<SwipeProfile[]>(queryKey);
    removeTop();
    if (pool.length - 1 <= 3) loadMore();
    try {
      await executor.executeAction(
        action,
        { action: action.action, data: { reason } },
        { objectId: c.profileId, silent: true }
      );
    } catch {
      queryClient.setQueryData(queryKey, snapshot);
    }
  }

  return { card, like, pass, report };
}
