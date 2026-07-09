import { useState } from 'react';
import { useNavigation } from '@react-navigation/native';
import { useForm } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/context/auth';
import {
  useGetApiProfilesMeSuspense,
  useGetApiDatingProfilesMeSuspense,
  getGetApiDatingProfilesMeQueryKey,
  getApiDatingProfilesMe,
} from '@/lib/api/generated/profiles/profiles';
import type { OwnDatingProfile } from '@/lib/api/generated/model';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import { View, Text, Pressable, SafeAreaView } from '@/lib/tw';
import { TextTabBar } from '@/components/TextTabBar';
import { WingStack } from '@/components/WingStack';
import { Button } from '@/components/Button';
import { AvatarPicker } from '@/components/AvatarPicker';
import { SettingsIcon } from '@/components/icons';
import ScreenSuspense from '@/components/ScreenSuspense';

import { AboutMeTab } from '@/features/profile/AboutMeTab';
import { PhotosTab } from '@/features/profile/PhotosTab';
import { PromptsTab } from '@/features/profile/PromptsTab';

function computeAge(dob: string): number | null {
  const d = new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age;
}

// ── Settings cog button (header right) ────────────────────────────────────────

function SettingsButton() {
  const navigation = useNavigation();
  return (
    <Pressable
      onPress={() => navigation.navigate('Settings')}
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
}: {
  name: string | null;
  userId: string;
  avatarUrl: string | null;
}) {
  const navigation = useNavigation();
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

      <View style={{ marginTop: 16, width: '100%' }}>
        <Button block variant="secondary" onPress={() => navigation.navigate('WingpeopleList')}>
          Wingpeople & Invitations
        </Button>
      </View>
    </View>
  );
}

// ── Root screen ───────────────────────────────────────────────────────────────

function ProfileScreenInner() {
  const navigation = useNavigation();
  const { userId } = useAuth();
  const queryClient = useQueryClient();

  const { data: profile } = useGetApiProfilesMeSuspense();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();
  const wingpeople = wingpeopleData.wingpeople;

  const [activeTab, setActiveTab] = useState(0);

  const form = useForm<OwnDatingProfile>({
    defaultValues: datingProfile ?? undefined,
  });

  const handleRefresh = async () => {
    const fresh = await getApiDatingProfilesMe();
    if (fresh) {
      form.reset(fresh);
      queryClient.setQueryData(getGetApiDatingProfilesMeQueryKey(), fresh);
    }
  };

  // ── Role = winger (this includes a dater who switched to "just winging" — their
  //    dating profile is kept but hidden until they switch back via Settings) ────
  if (profile?.role === 'winger') {
    return (
      <SafeAreaView className="flex-1 bg-canvas" edges={['top']}>
        <ProfileHeader />
        <WingerView
          name={profile.chosenName}
          userId={userId}
          avatarUrl={profile.avatarUrl ?? null}
        />
      </SafeAreaView>
    );
  }

  if (!datingProfile) return null; // routing should prevent this

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
            onPress={() => navigation.navigate('WingpeopleList')}
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
      {activeTab === 0 && <AboutMeTab data={datingProfile} />}
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
