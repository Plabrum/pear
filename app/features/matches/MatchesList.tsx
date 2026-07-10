import { useState } from 'react';
import { FlatList } from 'react-native';

import { View, Text, SafeAreaView } from '@/lib/tw';
import { useGetApiMatchesSuspense } from '@/lib/api/generated/matches/matches';
import type { MatchSummary } from '@/lib/api/generated/model';
import { LargeHeader } from '@/components/LargeHeader';
import { Pill } from '@/components/Pill';
import { MatchCard } from './MatchCard';
import { MatchSheet } from './MatchSheet';

export function MatchesList() {
  const { data: matches, refetch, isRefetching } = useGetApiMatchesSuspense();
  const [selectedMatch, setSelectedMatch] = useState<MatchSummary | null>(null);
  const newCount = matches.filter((m) => !m.hasMessages).length;

  return (
    <SafeAreaView className="flex-1 bg-background">
      <FlatList
        data={matches}
        keyExtractor={(item) => item.matchId}
        numColumns={2}
        columnWrapperStyle={{ gap: 12 }}
        contentContainerStyle={{ padding: 16, paddingBottom: 32, gap: 12 }}
        onRefresh={refetch}
        refreshing={isRefetching}
        ListHeaderComponent={
          <View style={{ marginHorizontal: -16, marginTop: -16, marginBottom: 4 }}>
            <LargeHeader
              title="Matches"
              right={
                newCount > 0 ? <Pill tone="leaf" size="sm" label={`${newCount} new`} /> : undefined
              }
            />
            <View style={{ paddingHorizontal: 20, paddingBottom: 8 }}>
              <Text className="text-ink-dim" style={{ fontSize: 13 }}>
                People who said yes. Pick one to nudge.
              </Text>
            </View>
          </View>
        }
        ListEmptyComponent={
          <View className="flex-1 items-center justify-center p-8">
            <Text
              className="text-ink"
              style={{
                fontFamily: 'DMSerifDisplay',
                fontSize: 22,
                letterSpacing: -0.4,
                textAlign: 'center',
              }}
            >
              No matches yet.
            </Text>
            <Text
              className="text-ink-mid"
              style={{
                fontSize: 14,
                lineHeight: 21,
                marginTop: 8,
                textAlign: 'center',
              }}
            >
              Keep swiping in Discover.
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <View className="flex-1">
            <MatchCard match={item} onPress={() => setSelectedMatch(item)} />
          </View>
        )}
      />
      <MatchSheet
        match={selectedMatch}
        visible={selectedMatch != null}
        onClose={() => setSelectedMatch(null)}
      />
    </SafeAreaView>
  );
}
