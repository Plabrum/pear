import { useCallback, useState } from 'react';
import { useRouter } from 'expo-router';
import { toast } from 'sonner-native';
import { useForm } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';
import Svg, { Path } from 'react-native-svg';

import { useAuth } from '@/context/auth';
import {
  useGetApiProfilesMeSuspense,
  useGetApiDatingProfilesMeSuspense,
  patchApiProfilesMe,
  patchApiDatingProfilesMe,
  getGetApiProfilesMeQueryKey,
  getGetApiDatingProfilesMeQueryKey,
  getApiDatingProfilesMe,
} from '@/lib/api/generated/profiles/profiles';
import type { OwnDatingProfileResponse } from '@/lib/api/generated/model';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import { View, Text, Pressable, SafeAreaView } from '@/lib/tw';
import { TextTabBar } from '@/components/ui/TextTabBar';
import { WingStack } from '@/components/ui/WingStack';
import { Sprout } from '@/components/ui/Sprout';
import { AvatarPicker } from '@/components/ui/AvatarPicker';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

import { AboutMeTab } from '@/components/profile/AboutMeTab';
import { PhotosTab } from '@/components/profile/PhotosTab';
import { PromptsTab } from '@/components/profile/PromptsTab';

const INK2 = '#4A4338';

function computeAge(dob: string): number | null {
  const d = new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age;
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function SettingsIcon({ size = 16, color = INK2 }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z" stroke={color} strokeWidth={1.6} />
      <Path
        d="M19.4 13a7.5 7.5 0 0 0 0-2l2-1.5-2-3.5-2.4.8a7.5 7.5 0 0 0-1.7-1l-.4-2.5h-4l-.4 2.5a7.5 7.5 0 0 0-1.7 1L6.6 6 4.6 9.5l2 1.5a7.5 7.5 0 0 0 0 2l-2 1.5 2 3.5 2.4-.8a7.5 7.5 0 0 0 1.7 1l.4 2.5h4l.4-2.5a7.5 7.5 0 0 0 1.7-1l2.4.8 2-3.5-2-1.5z"
        stroke={color}
        strokeWidth={1.4}
        strokeLinejoin="round"
      />
    </Svg>
  );
}

// ── Settings cog button (header right) ────────────────────────────────────────

function SettingsButton() {
  const router = useRouter();
  return (
    <Pressable
      onPress={() => router.push('/settings' as any)}
      className="flex-row items-center"
      style={{ gap: 6, paddingVertical: 6, paddingHorizontal: 10 }}
      hitSlop={8}
    >
      <SettingsIcon />
      <Text className="text-ink-mid" style={{ fontSize: 13, fontWeight: '600' }}>
        Settings
      </Text>
    </Pressable>
  );
}

// ── Header (serif title + Settings) ──────────────────────────────────────────

function ProfileHeader() {
  return (
    <View
      className="flex-row items-center justify-between"
      style={{ paddingHorizontal: 16, paddingTop: 6, paddingBottom: 8 }}
    >
      <Text className="font-serif text-ink" style={{ fontSize: 28, letterSpacing: -0.5 }}>
        Profile
      </Text>
      <SettingsButton />
    </View>
  );
}

// ── Winger view (role=winger or datingStatus=winging) ────────────────────────

function WingerView({
  name,
  userId,
  avatarUrl,
  banner,
}: {
  name: string | null;
  userId: string;
  avatarUrl: string | null;
  banner?: { title: string; sub: string; cta: string; onPress: () => void };
}) {
  const router = useRouter();
  return (
    <View className="flex-1 items-center justify-center" style={{ paddingHorizontal: 32 }}>
      <AvatarPicker name={name} avatarUrl={avatarUrl} size={84} userId={userId} />
      <Text
        className="font-serif text-ink"
        style={{ fontSize: 26, letterSpacing: -0.4, marginTop: 16 }}
      >
        {name ?? 'Winger'}
      </Text>
      <Text className="text-ink-dim" style={{ fontSize: 13, marginTop: 4 }}>
        Winger
      </Text>

      {banner ? (
        <View
          className="bg-surface"
          style={{
            marginTop: 28,
            padding: 16,
            borderRadius: 18,
            borderWidth: 1,
            borderColor: 'rgba(31,27,22,0.10)',
            width: '100%',
          }}
        >
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '600' }}>
            {banner.title}
          </Text>
          <Text className="text-ink-dim" style={{ fontSize: 12.5, marginTop: 4, lineHeight: 18 }}>
            {banner.sub}
          </Text>
          <View style={{ marginTop: 12 }}>
            <Sprout block size="sm" onPress={banner.onPress}>
              {banner.cta}
            </Sprout>
          </View>
        </View>
      ) : null}

      <View style={{ marginTop: 16, width: '100%' }}>
        <Sprout
          block
          variant="secondary"
          onPress={() => router.push('/(tabs)/profile/wingpeople' as any)}
        >
          Wingpeople & Invitations
        </Sprout>
      </View>
    </View>
  );
}

// ── Root screen ───────────────────────────────────────────────────────────────

function ProfileScreenInner() {
  const router = useRouter();
  const { userId } = useAuth();
  const queryClient = useQueryClient();

  const { data: profile } = useGetApiProfilesMeSuspense();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();
  const wingpeople = wingpeopleData.wingpeople;

  const [activeTab, setActiveTab] = useState(0);

  const form = useForm<NonNullable<OwnDatingProfileResponse>>({
    defaultValues: datingProfile ?? undefined,
  });

  const datingStatus = form.watch('datingStatus');

  const handleRefresh = useCallback(async () => {
    const fresh = await getApiDatingProfilesMe();
    if (fresh) {
      form.reset(fresh);
      queryClient.setQueryData(getGetApiDatingProfilesMeQueryKey(), fresh);
    }
  }, [queryClient, form]);

  // ── Role = winger ─────────────────────────────────────────────────────────
  if (profile?.role === 'winger') {
    const handleSwitchToDater = async () => {
      try {
        await patchApiProfilesMe({ role: 'dater' });
        queryClient.invalidateQueries({ queryKey: getGetApiProfilesMeQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
      } catch {
        toast.error("Couldn't switch profile. Try again.");
      }
    };

    return (
      <SafeAreaView className="flex-1 bg-canvas" edges={['top']}>
        <ProfileHeader />
        <WingerView
          name={profile.chosenName}
          userId={userId}
          avatarUrl={profile.avatarUrl ?? null}
          banner={{
            title: 'Want to start dating too?',
            sub: 'Set up a dater profile and start swiping.',
            cta: 'Start dating',
            onPress: handleSwitchToDater,
          }}
        />
      </SafeAreaView>
    );
  }

  if (!datingProfile) return null; // routing should prevent this

  // ── datingStatus = winging ───────────────────────────────────────────────
  if (datingStatus === 'winging') {
    const handleResumeDating = async () => {
      form.setValue('datingStatus', 'open');
      try {
        await patchApiDatingProfilesMe({ datingStatus: 'open' });
        queryClient.invalidateQueries({ queryKey: getGetApiProfilesMeQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
      } catch {
        form.setValue('datingStatus', 'winging');
        toast.error("Couldn't update status. Try again.");
      }
    };

    return (
      <SafeAreaView className="flex-1 bg-canvas" edges={['top']}>
        <ProfileHeader />
        <WingerView
          name={profile?.chosenName ?? null}
          userId={userId}
          avatarUrl={profile?.avatarUrl ?? null}
          banner={{
            title: "You're in winging mode",
            sub: 'Resume dating to set up your own profile.',
            cta: 'Resume dating',
            onPress: handleResumeDating,
          }}
        />
      </SafeAreaView>
    );
  }

  // ── Dater view ────────────────────────────────────────────────────────────
  const wingItems = wingpeople.map((w) => ({
    name: w.winger?.chosenName ?? '',
    photoUri: w.winger?.avatarUrl ?? null,
  }));

  const wingLabel = wingpeople.length
    ? `${wingpeople.length} wingperson${wingpeople.length !== 1 ? 's' : ''}`
    : 'Invite a wingperson';

  const age = profile?.dateOfBirth ? computeAge(profile.dateOfBirth) : null;
  const ageText = age != null ? `, ${age}` : '';

  return (
    <SafeAreaView className="flex-1 bg-canvas" edges={['top']}>
      <ProfileHeader />

      <View
        className="flex-row items-center"
        style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12, gap: 14 }}
      >
        <AvatarPicker
          name={profile?.chosenName ?? null}
          avatarUrl={profile?.avatarUrl ?? null}
          size={72}
          userId={userId}
        />
        <View style={{ flex: 1 }}>
          <Text
            className="font-serif text-ink"
            style={{ fontSize: 24, letterSpacing: -0.4 }}
            numberOfLines={1}
          >
            {(profile?.chosenName ?? '') + ageText}
          </Text>
          {datingProfile.city ? (
            <Text className="text-ink-dim" style={{ fontSize: 13, marginTop: 2 }}>
              {datingProfile.city}
            </Text>
          ) : null}
          <Pressable
            onPress={() => router.push('/(tabs)/profile/wingpeople' as any)}
            style={{ marginTop: 6, alignSelf: 'flex-start' }}
            hitSlop={6}
          >
            {wingItems.length > 0 ? (
              <WingStack items={wingItems} size={26} max={3} label={wingLabel} />
            ) : (
              <Text className="text-ink-dim" style={{ fontSize: 12.5, fontWeight: '500' }}>
                {wingLabel}
              </Text>
            )}
          </Pressable>
        </View>
      </View>

      <TextTabBar
        tabs={['About', 'Photos', 'Prompts']}
        active={activeTab}
        setActive={setActiveTab}
      />
      {activeTab === 0 && <AboutMeTab form={form} data={datingProfile} />}
      {activeTab === 1 && <PhotosTab form={form} data={datingProfile} onRefresh={handleRefresh} />}
      {activeTab === 2 && <PromptsTab form={form} onRefresh={handleRefresh} />}
    </SafeAreaView>
  );
}

export default function ProfileScreen() {
  return (
    <ScreenSuspense>
      <ProfileScreenInner />
    </ScreenSuspense>
  );
}
