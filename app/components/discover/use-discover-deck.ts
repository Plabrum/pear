import { useRef } from 'react';

import { useSwipeDeck } from '@/hooks/use-swipe-deck';

export type LikeResult =
  | { kind: 'match'; matchId: string }
  | { kind: 'liked' }
  | { kind: 'error' };

type Params = {
  /** Restrict the feed to profiles who already liked the dater. */
  likesYouOnly: boolean;
  /** Restrict the feed to winger hand-picks. */
  handPickedOnly: boolean;
  /**
   * Signature of the dater's search preferences — appended to the feed cache key
   * so changing preferences re-fetches the feed (the server derives results from
   * them but they aren't request params).
   */
  cacheKeySuffix: readonly unknown[];
};

/**
 * Discover swipe semantics composed on top of the shared {@link useSwipeDeck}.
 * `like` resolves to 'match' | 'liked' | 'error'; `pass`/`report` advance
 * optimistically with rollback on failure. A busy ref guards against
 * double-swipes while an action is in flight.
 */
export function useDiscoverDeck({ likesYouOnly, handPickedOnly, cacheKeySuffix }: Params) {
  const deck = useSwipeDeck({
    params: {
      ...(likesYouOnly ? { likesYouOnly: true } : {}),
      ...(handPickedOnly ? { wingerOnly: true } : {}),
    },
    actionGroup: 'dating_profile_swipe_actions',
    cacheKeySuffix,
    decrementsLikesCount: likesYouOnly,
  });
  const busyRef = useRef(false);

  const card = deck.currentCard;

  async function like(): Promise<LikeResult> {
    const c = deck.currentCard;
    if (!c || busyRef.current) return { kind: 'error' };
    busyRef.current = true;
    const res = await deck.run(c, 'like');
    busyRef.current = false;
    if (!res) return { kind: 'error' };
    return res.created_id != null ? { kind: 'match', matchId: res.created_id } : { kind: 'liked' };
  }

  async function pass(): Promise<void> {
    const c = deck.currentCard;
    if (!c || busyRef.current) return;
    busyRef.current = true;
    await deck.run(c, 'pass');
    busyRef.current = false;
  }

  async function report(reason: string): Promise<void> {
    const c = deck.currentCard;
    if (!c) return;
    await deck.run(c, 'report', { reason });
  }

  return { card, like, pass, report };
}
