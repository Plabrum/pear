import { useRef, useState } from 'react';
import type { SwipeProfile } from '@/lib/api/generated/model';
import { getApiDatingProfilesSwipe } from '@/lib/api/generated/dating-profiles/dating-profiles';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import { shortKey } from '@/lib/actions/types';

const PAGE_SIZE = 20;

export function useWingSwipe(daterId: string, initialPool: SwipeProfile[]) {
  const [pool, setPool] = useState(initialPool);
  const [index, setIndex] = useState(0);

  const offsetRef = useRef(initialPool.length);
  const loadingMoreRef = useRef(false);

  // Winger swipe writes flow through the action executor, driven by each card's
  // server actions[] (suggest / decline). `formContext` injects the daterId into
  // every body (both actions need it); `silent` keeps the deck's quiet-success UX
  // while the executor still handles invalidation (swipe pool, decisions, winger
  // tabs) + error toasts.
  const executor = useActionExecutor({
    actionGroup: 'dating_profile_swipe_actions',
    formContext: { daterId },
  });

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
    const action = (card.actions ?? []).find((a) => shortKey(a.action) === 'suggest');

    // Optimistic advance; trigger prefetch when nearing the end
    const newIndex = index + 1;
    setIndex(newIndex);
    if (newIndex >= pool.length - 3) loadMore();

    if (!action) return;
    try {
      // Suggest targets the DatingProfile (profileId); daterId comes from formContext.
      await executor.executeAction(action, { action: action.action, data: { note } }, {
        objectId: card.profileId,
        silent: true,
      });
    } catch {
      // Roll back on failure
      setIndex((prev) => prev - 1);
    }
  }

  async function decline(): Promise<void> {
    const card = pool[index];
    if (!card) return;
    const action = (card.actions ?? []).find((a) => shortKey(a.action) === 'decline');

    // Optimistic advance (fire-and-forget — no rollback); trigger prefetch near end
    const newIndex = index + 1;
    setIndex(newIndex);
    if (newIndex >= pool.length - 3) loadMore();

    if (action) {
      void executor
        .executeAction(action, undefined, { objectId: card.profileId, silent: true })
        .catch(() => {});
    }
  }

  return { pool, index, suggest: suggestCard, decline };
}
