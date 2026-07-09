import { StyleSheet } from 'react-native';
import { useState } from 'react';
import { useNavigation } from '@react-navigation/native';
import { toastError } from '@/lib/api/error-toast';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { useAuth } from '@/context/auth';
import {
  useGetApiProfilesMeSuspense,
  useGetApiDatingProfilesMeSuspense,
  getGetApiDatingProfilesMeQueryKey,
  getGetApiProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { switchToWinger, switchToDater, pauseDating, resumeDating } from '@/lib/api/actions';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import { authMeQueryKey } from '@/lib/auth-session';
import { View, Text, ScrollView, Pressable, SafeAreaView } from '@/lib/tw';
import { Sheet } from '@/components/Sheet';
import ScreenSuspense from '@/components/ScreenSuspense';
import { SectionLabel } from '@/components/SectionLabel';
import { colors } from '@/constants/theme';

const INK = colors.ink;
const INK3 = colors.inkDim;
const LINE = colors.divider;
const DANGER = colors.passRed;

const STATUS_OPTIONS = [
  { label: 'Open to Dating', value: 'open' as const },
  { label: 'Taking a Break', value: 'break' as const },
  { label: 'Just Winging', value: 'winging' as const },
];

const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  STATUS_OPTIONS.map((o) => [o.value, o.label])
);

type RowProps = {
  label: string;
  detail?: string;
  danger?: boolean;
  last?: boolean;
  onPress?: () => void;
};

function Row({ label, detail, danger, last, onPress }: RowProps) {
  return (
    <Pressable
      onPress={onPress}
      className="flex-row items-center"
      style={{
        minHeight: 50,
        paddingHorizontal: 16,
        borderBottomWidth: last ? 0 : StyleSheet.hairlineWidth,
        borderBottomColor: LINE,
      }}
    >
      <Text
        style={{
          flex: 1,
          fontSize: 15,
          fontWeight: '500',
          color: danger ? DANGER : INK,
        }}
      >
        {label}
      </Text>
      {detail ? (
        <Text className="text-ink-dim" style={{ fontSize: 14, marginRight: 8 }}>
          {detail}
        </Text>
      ) : null}
      {!danger ? <Ionicons name="chevron-forward" size={14} color={INK3} /> : null}
    </Pressable>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ marginBottom: 22 }}>
      <SectionLabel style={{ letterSpacing: 1.2, paddingHorizontal: 24, paddingTop: 18 }}>
        {title}
      </SectionLabel>
      <View
        className="bg-surface"
        style={{
          borderRadius: 18,
          marginHorizontal: 16,
          overflow: 'hidden',
          borderWidth: 1,
          borderColor: LINE,
        }}
      >
        {children}
      </View>
    </View>
  );
}

function SettingsScreenInner() {
  const navigation = useNavigation();
  const queryClient = useQueryClient();
  const { signOut } = useAuth();

  const { data: profile } = useGetApiProfilesMeSuspense();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();

  const [statusPickerVisible, setStatusPickerVisible] = useState(false);

  const wingCount = wingpeopleData.wingpeople.length;
  const phoneDetail = profile?.phoneNumber ?? undefined;

  // Project the two independent lifecycles (profile role + dating status) onto
  // the 3-way UI — "winging" is role === winger, not a dating_status value.
  const isWinger = profile?.role === 'winger';
  const currentStatus = isWinger ? 'winging' : datingProfile?.datingStatus;
  const statusDetail = currentStatus ? STATUS_LABEL[currentStatus] : undefined;

  const updateStatus = useMutation({
    // Returns whether the profile role (and therefore the tab shell) changed, so
    // onSuccess can dismiss Settings and drop the user into the new shell.
    mutationFn: async (target: 'open' | 'break' | 'winging'): Promise<{ roleChanged: boolean }> => {
      if (!profile) throw new Error('No profile');
      if (target === 'winging') {
        if (!isWinger) {
          await switchToWinger(profile.id);
          return { roleChanged: true };
        }
        return { roleChanged: false };
      }
      // target is open|break — first leave winger mode, then set the dating status.
      const roleChanged = isWinger;
      if (isWinger) await switchToDater(profile.id);
      if (datingProfile) {
        if (target === 'break' && datingProfile.datingStatus !== 'break') {
          await pauseDating(datingProfile.id);
        }
        if (target === 'open' && datingProfile.datingStatus !== 'open') {
          await resumeDating(datingProfile.id);
        }
      }
      return { roleChanged };
    },
    onSuccess: ({ roleChanged }) => {
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
      queryClient.invalidateQueries({ queryKey: getGetApiProfilesMeQueryKey() });
      // Refetch the session so the routing gate re-evaluates role and flips the
      // tab shell (dater ↔ winger) immediately.
      queryClient.invalidateQueries({ queryKey: authMeQueryKey });
      // Settings sits on top of the tab shell as a root route, so a role switch
      // swaps the shell underneath without the user seeing it. Dismiss Settings
      // so they land in the freshly-swapped tabs.
      if (roleChanged) navigation.goBack();
    },
    onError: (err) => toastError(err, "Couldn't update dating status. Try again."),
    onSettled: () => setStatusPickerVisible(false),
  });

  const handleSelectStatus = (value: 'open' | 'break' | 'winging') => {
    if (value === currentStatus) {
      setStatusPickerVisible(false);
      return;
    }
    updateStatus.mutate(value);
  };

  const handleLogOut = async () => {
    const { error } = await signOut();
    if (error) toastError(error, 'Could not log out. Please try again.');
  };

  return (
    <SafeAreaView className="flex-1 bg-canvas" edges={['top']}>
      <View
        className="flex-row items-center"
        style={{ paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, gap: 4 }}
      >
        <Pressable
          onPress={() => navigation.goBack()}
          hitSlop={12}
          style={{ padding: 8, marginLeft: -4 }}
        >
          <Ionicons name="chevron-back" size={22} color={INK} />
        </Pressable>
        <Text className="font-serif text-ink" style={{ fontSize: 26, letterSpacing: -0.4 }}>
          Settings
        </Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingTop: 4, paddingBottom: 100 }}
      >
        <Section title="Account">
          <Row label="Phone" detail={phoneDetail} />
          <Row label="Connected accounts" detail="Apple" />
          <Row
            label="Dating status"
            detail={statusDetail}
            onPress={datingProfile ? () => setStatusPickerVisible(true) : undefined}
            last
          />
        </Section>

        {/* ── Dating Status Picker ─────────────────────────────────────────────── */}
        <Sheet
          visible={statusPickerVisible}
          onClose={() => setStatusPickerVisible(false)}
          title="Dating status"
        >
          {STATUS_OPTIONS.map((opt) => {
            const selected = currentStatus === opt.value;
            return (
              <Pressable
                key={opt.value}
                onPress={() => !updateStatus.isPending && handleSelectStatus(opt.value)}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  paddingVertical: 16,
                  borderTopWidth: StyleSheet.hairlineWidth,
                  borderTopColor: LINE,
                  opacity: updateStatus.isPending ? 0.5 : 1,
                }}
              >
                <Text
                  style={{
                    flex: 1,
                    fontSize: 16,
                    fontWeight: selected ? '600' : '400',
                    color: selected ? colors.leaf : INK,
                  }}
                >
                  {opt.label}
                </Text>
                {selected ? <Ionicons name="checkmark" size={20} color={colors.leaf} /> : null}
              </Pressable>
            );
          })}
        </Sheet>

        <Section title="Wingpeople">
          <Row label="Who can suggest profiles" detail="Wingpeople" />
          <Row
            label="Manage wingpeople"
            detail={wingCount === 1 ? '1 active' : `${wingCount} active`}
            onPress={() =>
              navigation.navigate('DaterTabs', {
                screen: 'Profile',
                params: { screen: 'WingpeopleList' },
              })
            }
            last
          />
        </Section>

        <Section title="Notifications">
          <Row label="New matches" detail="On" />
          <Row label="Messages" detail="On" />
          <Row label="Wing suggestions" detail="On" />
          <Row label="Quiet hours" detail="10pm — 8am" last />
        </Section>

        <Section title="Privacy & legal">
          <Row label="Block list" />
          <Row label="Data & permissions" />
          <Row label="Terms" />
          <Row label="Privacy policy" last />
        </Section>

        <Section title="">
          <Row label="Take a break from dating" />
          <Row label="Log out" onPress={handleLogOut} />
          <Row label="Delete account" danger last />
        </Section>

        <Text
          className="text-ink-mid"
          style={{
            opacity: 0.5,
            fontSize: 11,
            textAlign: 'center',
            marginTop: 4,
          }}
        >
          Pear · v0
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

export default function SettingsScreen() {
  return (
    <ScreenSuspense>
      <SettingsScreenInner />
    </ScreenSuspense>
  );
}
