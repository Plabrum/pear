import { useRef, useState } from 'react';
import type { DecisionType, SwipeProfile } from '@/lib/api/generated/model';
import { like as likeProfile, pass as passProfile } from '@/lib/api/actions';

const PAGE_SIZE = 20;

export type LikeResult = 'match' | 'liked' | 'error';

export type PoolFetcher = (
  userId: string,
  pageSize: number,
  offset: number
) => Promise<SwipeProfile[]>;

export function useDiscover(
  fetchPool: PoolFetcher,
  userId: string | null,
  initialPool: SwipeProfile[]
) {
  const [pool, setPool] = useState(initialPool);
  const [index, setIndex] = useState(0);

  const offsetRef = useRef(initialPool.length);
  const loadingMoreRef = useRef(false);
  const swipingRef = useRef(false);

  async function loadMore() {
    if (!userId || loadingMoreRef.current) return;
    loadingMoreRef.current = true;
    const data = await fetchPool(userId, PAGE_SIZE, offsetRef.current);
    if (data.length > 0) {
      setPool((prev) => [...prev, ...data]);
      offsetRef.current += data.length;
    }
    loadingMoreRef.current = false;
  }

  async function decide(
    card: SwipeProfile,
    decision: DecisionType
  ): Promise<{ matched: boolean } | { error: true }> {
    try {
      // Like/pass on the target DatingProfile (profileId). A like covers both a
      // direct decision and acting on a winger's suggestion; a mutual match comes
      // back as the new match id in `created_id`.
      const res =
        decision === 'approved' ? await likeProfile(card.profileId) : await passProfile(card.profileId);
      return { matched: res.created_id != null };
    } catch {
      return { error: true };
    }
  }

  async function like(): Promise<LikeResult> {
    if (!userId || swipingRef.current) return 'error';
    const card = pool[index];
    if (!card) return 'error';
    swipingRef.current = true;

    // Optimistic advance; trigger prefetch when nearing the end
    const newIndex = index + 1;
    setIndex(newIndex);
    if (newIndex >= pool.length - 3) loadMore();

    const result = await decide(card, 'approved');
    swipingRef.current = false;

    if ('error' in result) {
      // Roll back on failure
      setIndex((prev) => prev - 1);
      return 'error';
    }
    return result.matched ? 'match' : 'liked';
  }

  async function pass(): Promise<void> {
    if (!userId || swipingRef.current) return;
    const card = pool[index];
    if (!card) return;
    swipingRef.current = true;

    // Optimistic advance; trigger prefetch when nearing the end
    const newIndex = index + 1;
    setIndex(newIndex);
    if (newIndex >= pool.length - 3) loadMore();

    await decide(card, 'declined');
    swipingRef.current = false;
  }

  return { pool, index, like, pass };
}
