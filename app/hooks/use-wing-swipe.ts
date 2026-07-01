import { useRef, useState } from 'react';
import type { SwipeProfile } from '@/lib/api/generated/model';
import { getApiDatingProfilesSwipe } from '@/lib/api/generated/dating-profiles/dating-profiles';
import { suggest } from '@/lib/api/actions';

const PAGE_SIZE = 20;

export function useWingSwipe(daterId: string, initialPool: SwipeProfile[]) {
  const [pool, setPool] = useState(initialPool);
  const [index, setIndex] = useState(0);

  const offsetRef = useRef(initialPool.length);
  const loadingMoreRef = useRef(false);

  async function loadMore() {
    if (loadingMoreRef.current) return;
    loadingMoreRef.current = true;
    const data = await getApiDatingProfilesSwipe({
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

  async function suggestCard(note: string | null): Promise<void> {
    const card = pool[index];
    if (!card) return;

    // Optimistic advance; trigger prefetch when nearing the end
    const newIndex = index + 1;
    setIndex(newIndex);
    if (newIndex >= pool.length - 3) loadMore();

    try {
      // Suggest targets the DatingProfile (profileId); daterId names who it's for.
      await suggest(card.profileId, { daterId, note, decision: null });
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
      await suggest(card.profileId, { daterId, decision: 'declined' });
    } catch {
      // Match legacy behavior: declines are fire-and-forget, no rollback.
    }
  }

  return { pool, index, suggest: suggestCard, decline };
}
