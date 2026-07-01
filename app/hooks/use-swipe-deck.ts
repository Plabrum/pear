import { useQueryClient, type InfiniteData } from '@tanstack/react-query';

import {
  getGetApiDatingProfilesSwipeCountQueryKey,
  getGetApiDatingProfilesSwipeInfiniteQueryKey,
  useGetApiDatingProfilesSwipeSuspenseInfinite,
} from '@/lib/api/generated/dating-profiles/dating-profiles';
import type {
  GetApiDatingProfilesSwipeParams,
  LikesYouCountResponse,
  SwipeProfile,
} from '@/lib/api/generated/model';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import { shortKey, type ActionExecutionResponse, type ActionGroupType } from '@/lib/actions/types';

const PAGE_SIZE = 20;
const PREFETCH_WITHIN = 3;

type SwipeFeed = InfiniteData<SwipeProfile[], number | undefined>;
/** Feed selectors the caller controls; `pageSize`/`pageOffset` are owned by the deck. */
type SwipeParams = Omit<GetApiDatingProfilesSwipeParams, 'pageSize' | 'pageOffset'>;

type Params = {
  /** Server-side feed selectors (likesYouOnly / wingerOnly / daterId …). */
  params: SwipeParams;
  /** The action group every swipe routes through. */
  actionGroup: ActionGroupType;
  /** Extra body fields injected into every action (e.g. `{ daterId }`). */
  formContext?: Record<string, unknown>;
  /**
   * Extra cache-identity tokens appended to the feed query key. The swipe
   * endpoint derives results from the dater's *server-side* preferences, which
   * aren't in `params` — pass a signature of them here so the feed re-fetches
   * when they change, instead of forcing a remount.
   */
  cacheKeySuffix?: readonly unknown[];
  /** Likes-you pool only: each decision also drops the unseen-likes badge count. */
  decrementsLikesCount?: boolean;
};

/**
 * Shared swipe-deck plumbing for the dater discover feed and the winger pool.
 * The feed *is* the cache: cards are paged in via `useInfiniteQuery` and consumed
 * by optimistically removing them from that cache (`run` → `drop`), so the
 * "current card" is always the head of the flattened pages — no local cursor,
 * no remount-to-reset. Callers compose their own swipe semantics (like/pass vs
 * suggest/decline) on top of `run`, which routes each action through the
 * executor (invalidation + error toasts) and rolls the card back on failure.
 */
export function useSwipeDeck({
  params,
  actionGroup,
  formContext,
  cacheKeySuffix,
  decrementsLikesCount,
}: Params) {
  const queryClient = useQueryClient();
  const queryParams = { ...params, pageSize: PAGE_SIZE };
  // Custom key so preferences (cacheKeySuffix) participate in cache identity
  // without being sent to the server; reused verbatim for the optimistic writes.
  const feedKey = [
    ...getGetApiDatingProfilesSwipeInfiniteQueryKey(queryParams),
    ...(cacheKeySuffix ?? []),
  ];
  const countKey = getGetApiDatingProfilesSwipeCountQueryKey();

  const { data, fetchNextPage, hasNextPage } = useGetApiDatingProfilesSwipeSuspenseInfinite(
    queryParams,
    {
      query: {
        queryKey: feedKey,
        initialPageParam: 0,
        getNextPageParam: (lastPage, allPages) =>
          lastPage.length < PAGE_SIZE ? undefined : allPages.flat().length,
      },
    }
  );

  const executor = useActionExecutor({ actionGroup, formContext });

  const pool = data.pages.flat();
  const currentCard = pool[0] ?? null;

  function bumpCount(delta: number) {
    if (!decrementsLikesCount) return;
    queryClient.setQueryData<LikesYouCountResponse>(countKey, (c) =>
      c ? { ...c, count: Math.max(0, c.count + delta) } : c
    );
  }

  function drop(profileId: string) {
    queryClient.setQueryData<SwipeFeed>(feedKey, (d) =>
      d ? { ...d, pages: d.pages.map((page) => page.filter((c) => c.profileId !== profileId)) } : d
    );
    bumpCount(-1);
  }

  function restore(card: SwipeProfile) {
    queryClient.setQueryData<SwipeFeed>(feedKey, (d) => {
      if (!d) return d;
      const [first = [], ...rest] = d.pages;
      return { ...d, pages: [[card, ...first], ...rest] };
    });
    bumpCount(1);
  }

  /**
   * Optimistically consume `card`: remove it from the feed (advancing the deck),
   * run its named server action, and — unless the caller opts out
   * (`rollback: false`, e.g. fire-and-forget winger decline) — put the card back
   * if the action fails. Resolves to the action response, or `undefined` if the
   * card has no such action or the action threw.
   */
  async function run(
    card: SwipeProfile,
    key: string,
    data?: Record<string, unknown>,
    opts?: { rollback?: boolean }
  ): Promise<ActionExecutionResponse | undefined> {
    const action = (card.actions ?? []).find((a) => shortKey(a.action) === key);
    if (!action) return undefined;

    drop(card.profileId);
    if (hasNextPage && pool.length - 1 <= PREFETCH_WITHIN) void fetchNextPage();

    const body = data ? { action: action.action, data } : undefined;
    try {
      return await executor.executeAction(action, body, { objectId: card.profileId, silent: true });
    } catch {
      if (opts?.rollback !== false) restore(card);
      return undefined;
    }
  }

  return { currentCard, remaining: pool.length, run };
}

export type SwipeDeck = ReturnType<typeof useSwipeDeck>;
