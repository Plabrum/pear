import { Suspense, useState } from 'react';
import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';

import PulseSpinner from '@/components/ui/PulseSpinner';
import { View, SafeAreaView } from '@/lib/tw';
import { colors } from '@/constants/theme';
import { useGetApiDatingProfilesSwipeCountSuspense } from '@/lib/api/generated/dating-profiles/dating-profiles';
import {
  useGetApiDatingProfilesMeSuspense,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import { LargeHeader } from '@/components/ui/LargeHeader';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

import type { Filter } from '@/components/discover/constants';
import { DiscoverFilters } from '@/components/discover/DiscoverFilters';
import { DiscoverPausedScreen } from '@/components/discover/DiscoverPausedScreen';
import { DiscoverDeck } from '@/components/discover/DiscoverDeck';
import {
  FilterEmptyState,
  WingEmptyState,
  NoMoreProfilesEmptyState,
} from '@/components/discover/EmptyStates';

function DiscoverContent() {
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const { data: likesYouCountResponse } = useGetApiDatingProfilesSwipeCountSuspense();
  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();
  const wingingFor = wingpeopleData.wingingFor;

  const [activeFilters, setActiveFilters] = useState<Filter[]>([]);

  const onResume = () =>
    queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });

  // `/dating-profiles/me` is `OwnDatingProfile | null` — null only before the
  // profile exists (onboarding). The gate guarantees one before discover, so a
  // null here is unexpected; treat it (and any non-open status) as paused. The
  // `!== 'open'` guard then narrows datingStatus to `'break'`, no cast needed.
  if (datingProfile == null) {
    return <DiscoverPausedScreen status="break" datingProfileId="" onResume={onResume} />;
  }
  if (datingProfile.datingStatus !== 'open') {
    return (
      <DiscoverPausedScreen
        status={datingProfile.datingStatus}
        datingProfileId={datingProfile.id}
        onResume={onResume}
      />
    );
  }

  // The unseen-likes badge: the feed's optimistic decisions keep this count fresh
  // (the deck pokes the count cache as it consumes likes), so read it directly.
  const likesYouCount = likesYouCountResponse.count;

  const toggleFilter = (key: Filter) =>
    setActiveFilters((prev) =>
      prev.includes(key) ? prev.filter((f) => f !== key) : [...prev, key]
    );
  const clearFilters = () => setActiveFilters([]);

  const wantsLikes = activeFilters.includes('likes');
  const wantsHandPicked = activeFilters.includes('handpicked');

  // The feed is derived server-side from the dater's search preferences, which
  // aren't request params — fold a signature of them into the deck's cache key so
  // changing preferences re-fetches the feed (no remount; filters flow through
  // their own props).
  const preferenceKey = [
    datingProfile.ageFrom,
    datingProfile.ageTo,
    datingProfile.interestedGender.join(','),
    datingProfile.religiousPreference ?? '',
  ];

  const emptyState =
    activeFilters.length === 0 ? (
      <NoMoreProfilesEmptyState />
    ) : wantsHandPicked && !wantsLikes ? (
      <WingEmptyState onInvite={() => router.push('/(tabs)/profile/wingpeople')} />
    ) : (
      <FilterEmptyState onClear={clearFilters} />
    );

  return (
    <SafeAreaView className="flex-1 bg-background">
      <LargeHeader title="Discover" />
      <DiscoverFilters
        active={activeFilters}
        onToggle={toggleFilter}
        onClearAll={clearFilters}
        counts={{ likes: likesYouCount }}
      />
      <Suspense
        fallback={
          <View className="flex-1 justify-center items-center p-6 gap-4">
            <PulseSpinner color={colors.leaf} />
          </View>
        }
      >
        <DiscoverDeck
          likesYouOnly={wantsLikes}
          handPickedOnly={wantsHandPicked}
          cacheKeySuffix={preferenceKey}
          emptyState={emptyState}
          wingingFor={wingingFor}
        />
      </Suspense>
    </SafeAreaView>
  );
}

export default function DiscoverScreen() {
  return (
    <ScreenSuspense>
      <DiscoverContent />
    </ScreenSuspense>
  );
}
