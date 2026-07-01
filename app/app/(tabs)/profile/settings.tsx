import { useRouter } from 'expo-router';
import { toast } from 'sonner-native';
import { StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { useAuth } from '@/context/auth';
import {
  useGetApiProfilesMeSuspense,
  useGetApiDatingProfilesMeSuspense,
} from '@/lib/api/generated/profiles/profiles';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import { View, Text, ScrollView, Pressable, SafeAreaView } from '@/lib/tw';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

const INK = '#1F1B16';
const INK3 = '#8B8170';
const LINE = 'rgba(31,27,22,0.10)';
const DANGER = '#A33';

// ── SectionLabel ──────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: string }) {
  if (!children) return <View style={{ height: 8 }} />;
  return (
    <Text
      className="text-ink-dim"
      style={{
        fontSize: 11,
        letterSpacing: 1.2,
        textTransform: 'uppercase',
        fontWeight: '600',
        paddingHorizontal: 24,
        paddingTop: 18,
        paddingBottom: 8,
      }}
    >
      {children}
    </Text>
  );
}

// ── Row ───────────────────────────────────────────────────────────────────────

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

// ── Section ───────────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ marginBottom: 22 }}>
      <SectionLabel>{title}</SectionLabel>
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

// ── Screen ────────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  break: 'On a break',
  winging: 'Winging only',
};

function SettingsScreenInner() {
  const router = useRouter();
  const { signOut } = useAuth();

  const { data: profile } = useGetApiProfilesMeSuspense();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();

  const wingCount = wingpeopleData.wingpeople.length;
  const phoneDetail = profile?.phoneNumber ?? undefined;
  const statusDetail = datingProfile?.datingStatus
    ? STATUS_LABEL[datingProfile.datingStatus]
    : undefined;

  const handleLogOut = async () => {
    const { error } = await signOut();
    if (error) toast.error('Could not log out. Please try again.');
  };

  return (
    <SafeAreaView className="flex-1 bg-canvas" edges={['top']}>
      <View
        className="flex-row items-center"
        style={{ paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, gap: 4 }}
      >
        <Pressable
          onPress={() => router.back()}
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
          <Row label="Dating status" detail={statusDetail} last />
        </Section>

        <Section title="Wingpeople">
          <Row label="Who can suggest profiles" detail="Wingpeople" />
          <Row
            label="Manage wingpeople"
            detail={wingCount === 1 ? '1 active' : `${wingCount} active`}
            onPress={() => router.push('/(tabs)/profile/wingpeople' as any)}
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
