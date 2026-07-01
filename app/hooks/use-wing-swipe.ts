import { useRef, useState } from 'react';
import type { WingProfile } from '@/lib/api/generated/model';
import { getApiWingPool } from '@/lib/api/generated/wing-pool/wing-pool';
import { postApiDecisionsSuggestions } from '@/lib/api/generated/decisions/decisions';

const PAGE_SIZE = 20;

export function useWingSwipe(daterId: string, initialPool: WingProfile[]) {
  const [pool, setPool] = useState(initialPool);
  const [index, setIndex] = useState(0);

  const offsetRef = useRef(initialPool.length);
  const loadingMoreRef = useRef(false);

  async function loadMore() {
    if (loadingMoreRef.current) return;
    loadingMoreRef.current = true;
    const data = await getApiWingPool({
      daterId,
      pageSize: PAGE_SIZE,
      pageOffset: offsetRef.current,
    });
    if (data.length > 0) {
      setPool((prev) => [...prev, ...data]);
      offsetRef.current += data.length;
    }
    loadingMoreRef.current = false;
  }

  async function suggest(note: string | null): Promise<void> {
    const card = pool[index];
    if (!card) return;

    // Optimistic advance; trigger prefetch when nearing the end
    const newIndex = index + 1;
    setIndex(newIndex);
    if (newIndex >= pool.length - 3) loadMore();

    try {
      await postApiDecisionsSuggestions({
        daterId,
        recipientId: card.userId,
        note,
        decision: null,
      });
    } catch {
      // Roll back on failure
      setIndex((prev) => prev - 1);
    }
  }

  async function decline(): Promise<void> {
    const card = pool[index];
    if (!card) return;

    // Optimistic advance (fire-and-forget — no rollback needed); trigger prefetch when nearing end
    const newIndex = index + 1;
    setIndex(newIndex);
    if (newIndex >= pool.length - 3) loadMore();

    try {
      await postApiDecisionsSuggestions({
        daterId,
        recipientId: card.userId,
        decision: 'declined',
      });
    } catch {
      // Match legacy behavior: declines are fire-and-forget, no rollback.
    }
  }

  return { pool, index, suggest, decline };
}
