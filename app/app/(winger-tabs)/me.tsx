import { useRouter } from 'expo-router';

import { useAuth } from '@/context/auth';
import { colors } from '@/constants/theme';
import { View, Text, Pressable, SafeAreaView } from '@/lib/tw';
import { SettingsIcon } from '@/components/ui/icons';
import { AvatarPicker } from '@/components/ui/AvatarPicker';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { useGetApiProfilesMeSuspense } from '@/lib/api/generated/profiles/profiles';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';

function MeContent() {
  const router = useRouter();
  const { userId } = useAuth();

  const { data: profile } = useGetApiProfilesMeSuspense();
  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();

  const wingingForCount = wingpeopleData.wingingFor.length;
  const subtitle = wingingForCount > 0 ? `Winging for ${wingingForCount}` : 'Winger';

  return (
    <>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <View className="px-4 pt-2 pb-1 flex-row items-center justify-between">
        <Text className="font-serif text-ink" style={{ fontSize: 28, letterSpacing: -0.5 }}>
          Me
        </Text>
        <Pressable
          onPress={() => router.push('/settings' as any)}
          hitSlop={8}
          style={{ padding: 6 }}
        >
          <SettingsIcon size={22} color={colors.inkMid} />
        </Pressable>
      </View>

      {/* ── Centered content ────────────────────────────────────────────────── */}
      <View
        style={{
          flex: 1,
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: 16,
          gap: 24,
        }}
      >
        {/* Avatar + name + status */}
        <View style={{ alignItems: 'center', gap: 10 }}>
          <AvatarPicker
            name={profile?.chosenName ?? ''}
            avatarUrl={profile?.avatarUrl ?? null}
            size={120}
            userId={userId}
          />
          <Text className="font-serif text-ink" style={{ fontSize: 28, letterSpacing: -0.4 }}>
            {profile?.chosenName ?? 'Winger'}
          </Text>
          <Text className="text-ink-dim" style={{ fontSize: 15 }}>
            {subtitle}
          </Text>
        </View>

        {/* Wing card */}
        <View className="bg-ink" style={{ borderRadius: 20, padding: 18, width: '100%' }}>
          <Text
            className="text-surface"
            style={{
              fontSize: 10,
              letterSpacing: 1.6,
              textTransform: 'uppercase',
              opacity: 0.7,
              marginBottom: 8,
            }}
          >
            Your wing card
          </Text>
          <Text
            className="font-serif text-surface"
            style={{ fontSize: 28, lineHeight: 32, letterSpacing: -0.5 }}
          >
            {wingingForCount} {wingingForCount === 1 ? 'friend trusts' : 'friends trust'} your taste
          </Text>
          <Text className="text-surface" style={{ fontSize: 12.5, opacity: 0.7, marginTop: 6 }}>
            Send picks from Friends. Track replies in Activity.
          </Text>
        </View>
      </View>
    </>
  );
}

export default function MeScreen() {
  return (
    <SafeAreaView className="flex-1 bg-page" edges={['top']}>
      <ScreenSuspense>
        <MeContent />
      </ScreenSuspense>
    </SafeAreaView>
  );
}
