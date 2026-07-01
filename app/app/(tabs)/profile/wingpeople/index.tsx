import { Suspense, useState } from 'react';
import { Alert } from 'react-native';
import Splash from '@/components/ui/Splash';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { Sprout } from '@/components/ui/Sprout';
import { View, Text, ScrollView, SafeAreaView, Pressable } from '@/lib/tw';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import { shortKey, type ActionDTO } from '@/lib/actions/types';
import { InviteWingpersonSheet } from '@/components/wingpeople/InviteWingpersonSheet';
import { SectionLabel } from '@/components/ui/SectionLabel';
import { colors } from '@/constants/theme';

// Preserve this screen's slightly tighter section heading spacing.
const sectionLabelStyle = { letterSpacing: 1.2, paddingTop: 18 };

// ── Inner content (Suspense boundary child) ────────────────────────────────────

interface ContentProps {
  onOpenInvite: () => void;
}

function WingpeopleContent({ onOpenInvite }: ContentProps) {
  const router = useRouter();
  const { data } = useGetApiWingpeopleSuspense();
  const { wingpeople, invitations, wingingFor, sentInvitations, weeklyCounts } = data;

  // All wingperson writes flow through the action executor, driven by each row's
  // server actions[] (contact_actions: accept / decline / remove). `silent` keeps
  // the quiet-success UX; the executor owns invalidation + error toasts.
  const executor = useActionExecutor({ actionGroup: 'contact_actions' });

  type Row = { id: string; actions?: ActionDTO[] | null };

  const run = (row: Row, key: string) => {
    const action = (row.actions ?? []).find((a) => shortKey(a.action) === key);
    if (action) {
      void executor
        .executeAction(action, undefined, { objectId: row.id, silent: true })
        .catch(() => {});
    }
  };

  const handleAccept = (inv: Row) => run(inv, 'accept');
  const handleDecline = (inv: Row) => run(inv, 'decline');

  const handleCancelInvite = (inv: Row) => {
    Alert.alert('Cancel invite?', 'This will withdraw the invitation.', [
      { text: 'Keep', style: 'cancel' },
      { text: 'Cancel Invite', style: 'destructive', onPress: () => run(inv, 'remove') },
    ]);
  };

  const handleRemove = (w: Row) => {
    Alert.alert('Remove wingperson?', 'They will no longer swipe on your behalf.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Remove', style: 'destructive', onPress: () => run(w, 'remove') },
    ]);
  };

  return (
    <ScrollView contentContainerStyle={{ paddingBottom: 32 }}>
      {/* ── Section 1: Your Wingpeople ─────────────────────────────────────── */}
      <SectionLabel
        style={sectionLabelStyle}
      >{`Your wingpeople · ${wingpeople.length} of 5`}</SectionLabel>

      {wingpeople.length === 0 ? (
        <Text
          className="text-ink-dim"
          style={{
            fontSize: 13,
            paddingHorizontal: 16,
            paddingVertical: 12,
            lineHeight: 20,
          }}
        >
          No wingpeople yet. Invite a trusted friend to swipe for you.
        </Text>
      ) : (
        <View style={{ paddingHorizontal: 16, gap: 10 }}>
          {wingpeople.map((w) => {
            const name = w.winger?.chosenName ?? 'Unknown';
            const count = weeklyCounts[w.id] ?? 0;
            return (
              <Pressable
                key={w.id}
                onLongPress={() => handleRemove(w)}
                delayLongPress={500}
                className="bg-surface"
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 12,
                  paddingHorizontal: 12,
                  paddingVertical: 10,
                  borderRadius: 16,
                  borderWidth: 1,
                  borderColor: colors.divider,
                }}
              >
                <FaceAvatar name={name} size={44} photoUri={w.winger?.avatarUrl ?? null} />
                <View style={{ flex: 1 }}>
                  <Text className="text-ink" style={{ fontSize: 14.5, fontWeight: '600' }}>
                    {name}
                  </Text>
                  <Text className="text-ink-dim" style={{ fontSize: 12, marginTop: 2 }}>
                    {count} pick{count !== 1 ? 's' : ''} this week
                  </Text>
                </View>
                <Pressable hitSlop={8} style={{ padding: 6 }} onPress={() => handleRemove(w)}>
                  <Ionicons name="ellipsis-vertical" size={18} color={colors.inkDim} />
                </Pressable>
              </Pressable>
            );
          })}
        </View>
      )}

      {/* ── Section 2: Sent Invites ─────────────────────────────────────────── */}
      {sentInvitations.length > 0 && (
        <>
          <SectionLabel
            style={sectionLabelStyle}
          >{`Sent invites · ${sentInvitations.length}`}</SectionLabel>
          <View style={{ paddingHorizontal: 16, gap: 10 }}>
            {sentInvitations.map((inv) => {
              const displayName = inv.winger?.chosenName ?? inv.phoneNumber ?? 'Unknown';
              return (
                <View
                  key={inv.id}
                  className="bg-surface"
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 12,
                    paddingHorizontal: 12,
                    paddingVertical: 10,
                    borderRadius: 16,
                    borderWidth: 1,
                    borderColor: colors.divider,
                  }}
                >
                  <FaceAvatar name={displayName} size={44} />
                  <View style={{ flex: 1 }}>
                    <Text className="text-ink" style={{ fontSize: 14.5, fontWeight: '600' }}>
                      {displayName}
                    </Text>
                    <Text className="text-ink-dim" style={{ fontSize: 12, marginTop: 2 }}>
                      Invite pending
                    </Text>
                  </View>
                  <Sprout size="sm" variant="secondary" onPress={() => handleCancelInvite(inv)}>
                    Cancel
                  </Sprout>
                </View>
              );
            })}
          </View>
        </>
      )}

      {/* ── Section 3: Invitations ──────────────────────────────────────────── */}
      {invitations.length > 0 && (
        <>
          <SectionLabel
            style={sectionLabelStyle}
          >{`Invitations · ${invitations.length}`}</SectionLabel>
          <View style={{ paddingHorizontal: 16, gap: 10 }}>
            {invitations.map((inv) => {
              const name = inv.dater?.chosenName ?? 'Unknown';
              const firstName = name.split(' ')[0] || name;
              return (
                <View
                  key={inv.id}
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 10,
                    paddingHorizontal: 14,
                    paddingVertical: 12,
                    backgroundColor: colors.leafSoft,
                    borderRadius: 16,
                  }}
                >
                  <FaceAvatar name={name} size={42} />
                  <View style={{ flex: 1 }}>
                    <Text className="text-ink" style={{ fontSize: 14, fontWeight: '600' }}>
                      {firstName} wants you to wing
                    </Text>
                    <Text className="text-ink-mid" style={{ fontSize: 12, marginTop: 2 }}>
                      You{"'"}d help curate {firstName}
                      {"'"}s feed.
                    </Text>
                  </View>
                  <Sprout size="sm" variant="secondary" onPress={() => handleDecline(inv)}>
                    Decline
                  </Sprout>
                  <Sprout size="sm" onPress={() => handleAccept(inv)}>
                    Accept
                  </Sprout>
                </View>
              );
            })}
          </View>
        </>
      )}

      {/* ── Section 4: You're Winging For ──────────────────────────────────── */}
      {wingingFor.length > 0 && (
        <>
          <SectionLabel style={sectionLabelStyle}>{`You're winging for`}</SectionLabel>
          <View style={{ paddingHorizontal: 16, gap: 12 }}>
            {wingingFor.map((wf) => {
              const name = wf.dater?.chosenName ?? 'Unknown';
              const firstName = name.split(' ')[0] || name;
              const daterId = wf.dater?.id;
              return (
                <View
                  key={wf.id}
                  className="bg-surface"
                  style={{
                    borderRadius: 18,
                    borderWidth: 1,
                    borderColor: colors.divider,
                    padding: 14,
                  }}
                >
                  <View
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 12,
                      marginBottom: 12,
                    }}
                  >
                    <FaceAvatar name={name} size={48} photoUri={wf.dater?.avatarUrl ?? null} />
                    <View style={{ flex: 1 }}>
                      <Text className="text-ink" style={{ fontSize: 15, fontWeight: '600' }}>
                        {name}
                      </Text>
                      <Text className="text-ink-dim" style={{ fontSize: 12, marginTop: 2 }}>
                        Help {firstName} build their profile and find matches.
                      </Text>
                    </View>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    <View style={{ flex: 1 }}>
                      <Sprout
                        block
                        size="sm"
                        variant="secondary"
                        onPress={() =>
                          router.push(
                            `/(tabs)/profile/wingpeople/contribute?daterId=${daterId}` as any
                          )
                        }
                      >
                        Add to profile
                      </Sprout>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Sprout
                        block
                        size="sm"
                        icon={<Ionicons name="heart" size={14} color={colors.white} />}
                        onPress={() =>
                          router.push(
                            `/(tabs)/profile/wingpeople/wingswipe?daterId=${daterId}` as any
                          )
                        }
                      >
                        Swipe for {firstName}
                      </Sprout>
                    </View>
                  </View>
                </View>
              );
            })}
          </View>
        </>
      )}
    </ScrollView>
  );
}

// ── Outer screen ──────────────────────────────────────────────────────────────

export default function WingpeopleScreen() {
  const router = useRouter();
  const [inviteVisible, setInviteVisible] = useState(false);

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
          <Ionicons name="chevron-back" size={22} color={colors.ink} />
        </Pressable>
        <Text
          className="font-serif text-ink"
          style={{ fontSize: 26, letterSpacing: -0.4, flex: 1 }}
        >
          Wingpeople
        </Text>
        <Sprout
          size="sm"
          icon={<Ionicons name="add" size={14} color={colors.white} />}
          onPress={() => setInviteVisible(true)}
        >
          Invite
        </Sprout>
      </View>

      <Suspense fallback={<Splash variant="spinner" />}>
        <WingpeopleContent onOpenInvite={() => setInviteVisible(true)} />
      </Suspense>

      <InviteWingpersonSheet visible={inviteVisible} onClose={() => setInviteVisible(false)} />
    </SafeAreaView>
  );
}
