import { useRouter } from 'expo-router';
import { toast } from 'sonner-native';
import { useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';

import { useAuth } from '@/context/auth';
import { View, Text, Pressable, ScrollView, SafeAreaView } from '@/lib/tw';
import { AvatarPicker } from '@/components/ui/AvatarPicker';
import { Sprout } from '@/components/ui/Sprout';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import {
  getGetApiDatingProfilesMeQueryKey,
  getGetApiProfilesMeQueryKey,
  patchApiDatingProfilesMe,
  patchApiProfilesMe,
  useGetApiDatingProfilesMeSuspense,
  useGetApiProfilesMeSuspense,
} from '@/lib/api/generated/profiles/profiles';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';

function MeContent() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { userId } = useAuth();

  const { data: profile } = useGetApiProfilesMeSuspense();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();

  const wingingForCount = wingpeopleData.wingingFor.length;

  const handleSwitchToDater = async () => {
    try {
      if (profile?.role === 'winger') {
        await patchApiProfilesMe({ role: 'dater' });
      } else if (datingProfile?.datingStatus === 'winging') {
        await patchApiDatingProfilesMe({ datingStatus: 'open' });
      }
      queryClient.invalidateQueries({ queryKey: getGetApiProfilesMeQueryKey() });
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch {
      toast.error("Couldn't switch profile. Try again.");
    }
  };

  const subtitle = wingingForCount > 0 ? `Winging for ${wingingForCount}` : 'Winger';

  return (
    <ScrollView contentContainerClassName="pb-32">
      <View className="px-4 pt-2 pb-1 flex-row items-center justify-between">
        <Text className="font-serif text-ink" style={{ fontSize: 28, letterSpacing: -0.5 }}>
          Me
        </Text>
        <Pressable
          onPress={() => router.push('/settings' as any)}
          hitSlop={8}
          style={{ padding: 6 }}
        >
          <Ionicons name="settings-outline" size={22} color="#4A4338" />
        </Pressable>
      </View>

      <View className="px-4 pt-3 pb-4 flex-row items-center" style={{ gap: 14 }}>
        <AvatarPicker
          name={profile?.chosenName ?? ''}
          avatarUrl={profile?.avatarUrl ?? null}
          size={64}
          userId={userId}
        />
        <View style={{ flex: 1 }}>
          <Text className="font-serif text-ink" style={{ fontSize: 22, letterSpacing: -0.4 }}>
            {profile?.chosenName ?? 'Winger'}
          </Text>
          <Text className="text-sm mt-0.5 text-ink-dim">{subtitle}</Text>
        </View>
      </View>

      <View className="px-4">
        <View
          className="bg-ink"
          style={{
            borderRadius: 20,
            padding: 18,
          }}
        >
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
            Send picks from Scout. Track replies in Activity.
          </Text>
        </View>
      </View>

      <Text className="text-xs font-semibold uppercase tracking-[0.6px] px-5 pt-6 pb-2 text-fg-muted">
        Settings
      </Text>
      <View className="px-4" style={{ gap: 8 }}>
        <Pressable
          onPress={() => router.push('/settings' as any)}
          className="bg-white rounded-xl px-3.5 py-3 flex-row items-center"
          style={{ borderWidth: 1, borderColor: 'rgba(31,27,22,0.06)', gap: 10 }}
        >
          <Text className="flex-1 text-sm text-ink">Account & notifications</Text>
          <Text className="text-ink-dim">›</Text>
        </Pressable>
      </View>

      {profile?.role !== 'winger' && datingProfile?.datingStatus === 'winging' ? (
        <View className="px-4 mt-6">
          <Sprout block variant="secondary" onPress={handleSwitchToDater}>
            Resume dating
          </Sprout>
        </View>
      ) : null}

      {profile?.role === 'winger' ? (
        <View className="px-4 mt-6">
          <Text className="text-sm mb-2 text-ink-dim">
            Want to date too? Spin up your own profile.
          </Text>
          <Sprout block variant="secondary" onPress={handleSwitchToDater}>
            Start dating
          </Sprout>
        </View>
      ) : null}
    </ScrollView>
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
