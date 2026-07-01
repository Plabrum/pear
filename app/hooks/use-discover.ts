import { useRef, useState } from 'react';
import type { DirectDecisionRequestDecision, DiscoverProfile } from '@/lib/api/generated/model';
import {
  postApiDecisions,
  postApiDecisionsSuggestionsAct,
} from '@/lib/api/generated/decisions/decisions';

const PAGE_SIZE = 20;

export type LikeResult = 'match' | 'liked' | 'error';

export type PoolFetcher = (
  userId: string,
  pageSize: number,
  offset: number
) => Promise<DiscoverProfile[]>;

export function useDiscover(
  fetchPool: PoolFetcher,
  userId: string | null,
  initialPool: DiscoverProfile[]
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
    card: DiscoverProfile,
    decision: DirectDecisionRequestDecision
  ): Promise<{ matched: boolean } | { error: true }> {
    try {
      if (card.suggestedBy) {
        const res = await postApiDecisionsSuggestionsAct({
          recipientId: card.userId,
          decision,
        });
        return { matched: res.match != null };
      }
      const res = await postApiDecisions({ recipientId: card.userId, decision });
      return { matched: res.match != null };
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

  async function actOnSuggestion(decision: DirectDecisionRequestDecision) {
    if (decision === 'approved') return like();
    return pass();
  }

  return { pool, index, like, pass, actOnSuggestion };
}
