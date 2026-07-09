import React, { useState } from 'react';
import { useNavigation } from '@react-navigation/native';

import { View } from '@/lib/tw';
import type { SwipeProfile, WingingForRow } from '@/lib/api/generated/model';

import { useDiscoverDeck } from './use-discover-deck';
import { DiscoverCard } from './DiscoverCard';
import { MatchOverlay } from './MatchOverlay';

type DiscoverDeckProps = {
  likesYouOnly: boolean;
  handPickedOnly: boolean;
  /** Preference signature appended to the feed cache key (see useDiscoverDeck). */
  cacheKeySuffix: readonly unknown[];
  emptyState: React.ReactNode;
  wingingFor: WingingForRow[];
};

/**
 * The dater discover deck: the feed selectors (`likesYouOnly` / `handPickedOnly`)
 * flow straight into the query key, so toggling filters re-fetches the right feed
 * with no remount. Renders the head card and a match overlay on a mutual like.
 */
export function DiscoverDeck({
  likesYouOnly,
  handPickedOnly,
  cacheKeySuffix,
  emptyState,
  wingingFor,
}: DiscoverDeckProps) {
  const navigation = useNavigation();
  const { card, like, pass, report } = useDiscoverDeck({
    likesYouOnly,
    handPickedOnly,
    cacheKeySuffix,
  });
  const [match, setMatch] = useState<{ card: SwipeProfile; matchId: string } | null>(null);

  async function handleLike() {
    if (!card) return;
    const decidedCard = card;
    const result = await like();
    if (result.kind === 'match') setMatch({ card: decidedCard, matchId: result.matchId });
  }

  function openMatchChat() {
    if (!match) return;
    const { card: matchedCard, matchId } = match;
    setMatch(null);
    navigation.navigate('Messages', {
      screen: 'MessageThread',
      params: {
        matchId,
        otherName: matchedCard.chosenName,
        otherUserId: matchedCard.userId,
      },
    });
  }

  if (card == null) {
    return <View className="flex-1 px-3.5 pb-2">{emptyState}</View>;
  }

  return (
    <>
      <View className="flex-1 px-3.5 pb-2">
        <DiscoverCard
          card={card}
          onLike={handleLike}
          onPass={pass}
          onReport={report}
          wingingFor={wingingFor}
        />
      </View>
      {match && (
        <MatchOverlay card={match.card} onClose={() => setMatch(null)} onMessage={openMatchChat} />
      )}
    </>
  );
}
