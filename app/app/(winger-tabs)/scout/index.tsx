import { StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { colors } from '@/constants/theme';
import { View, Text, Pressable, ScrollView, SafeAreaView } from '@/lib/tw';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';

function ScoutContent() {
  const router = useRouter();
  const { data } = useGetApiWingpeopleSuspense();
  const { wingingFor, weeklyCounts } = data;

  const goScout = (daterId: string) => router.push(`/(winger-tabs)/scout/${daterId}` as any);

  return (
    <ScrollView contentContainerClassName="pb-32">
      <View className="px-4 pt-2 pb-1">
        <Text className="font-serif text-ink" style={{ fontSize: 28, letterSpacing: -0.5 }}>
          Scout
        </Text>
      </View>
      <Text className="px-4 pb-3 text-sm text-ink-dim">
        Find people for someone you wing for. Pick the friend you have in mind.
      </Text>

      {wingingFor.length === 0 ? (
        <View
          className="mx-4 p-4 rounded-2xl"
          style={{ borderWidth: 1, borderColor: colors.divider, borderStyle: 'dashed' }}
        >
          <Text className="text-xs uppercase mb-1 text-ink-dim" style={{ letterSpacing: 1.4 }}>
            No friends yet
          </Text>
          <Text className="text-sm leading-5 text-ink-mid">
            When a dater invites you to wing for them, you can scout for them here.
          </Text>
        </View>
      ) : (
        <View className="px-4" style={{ gap: 10 }}>
          {wingingFor.map((wf) => {
            const name = wf.dater?.chosenName ?? 'Unknown';
            const sent = weeklyCounts[wf.id] ?? 0;
            const daterId = wf.dater?.id;
            return (
              <Pressable
                key={wf.id}
                onPress={() => daterId && goScout(daterId)}
                className="bg-white rounded-2xl px-3.5 py-3"
                style={{
                  borderWidth: StyleSheet.hairlineWidth,
                  borderColor: colors.divider,
                }}
              >
                <View className="flex-row items-center" style={{ gap: 12 }}>
                  <FaceAvatar name={name} size={44} photoUri={wf.dater?.avatarUrl ?? null} />
                  <View className="flex-1">
                    <Text className="text-base font-semibold text-ink">{name}</Text>
                    <Text className="text-xs mt-0.5 text-ink-dim">
                      {sent} pick{sent !== 1 ? 's' : ''} this week
                    </Text>
                  </View>
                  <Text className="text-ink-dim" style={{ fontSize: 22 }}>
                    ›
                  </Text>
                </View>
              </Pressable>
            );
          })}
        </View>
      )}

      <View
        className="mx-4 mt-6 p-4 rounded-2xl"
        style={{ borderWidth: 1, borderColor: colors.divider, borderStyle: 'dashed' }}
      >
        <Text className="text-xs uppercase mb-1.5 text-ink-dim" style={{ letterSpacing: 1.4 }}>
          Tip
        </Text>
        <Text className="text-sm leading-5 text-ink-mid">
          Your suggestions arrive in your friend{"'"}s hand-picked pile. They still choose. You{"'"}
          re a scout, not a matchmaker.
        </Text>
      </View>
    </ScrollView>
  );
}

export default function ScoutScreen() {
  return (
    <SafeAreaView className="flex-1 bg-page" edges={['top']}>
      <ScreenSuspense>
        <ScoutContent />
      </ScreenSuspense>
    </SafeAreaView>
  );
}
