import { useState } from 'react';
import { StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { colors } from '@/constants/theme';
import { View, Text, Pressable, ScrollView, SafeAreaView } from '@/lib/tw';
import { FaceAvatar } from '@/components/FaceAvatar';
import { PlusIcon } from '@/components/icons';
import { Sprout } from '@/components/Sprout';
import ScreenSuspense from '@/components/ScreenSuspense';
import { InviteWingpersonSheet } from '@/features/wingpeople/InviteWingpersonSheet';
import {
  getGetApiWingpeopleQueryKey,
  useGetApiWingpeopleSuspense,
} from '@/lib/api/generated/contacts/contacts';
import { acceptWingperson, declineWingperson } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';

function SectionHeader({ title }: { title: string }) {
  return (
    <Text className="text-xs font-semibold uppercase tracking-[0.6px] px-5 pt-6 pb-2 text-fg-muted">
      {title}
    </Text>
  );
}

function FriendsContent({ onOpenInvite }: { onOpenInvite: () => void }) {
  const navigation = useNavigation();
  const queryClient = useQueryClient();
  const { data } = useGetApiWingpeopleSuspense();
  const { wingingFor, invitations, weeklyCounts } = data;

  const acceptMutation = useMutation({ mutationFn: acceptWingperson });
  const declineMutation = useMutation({ mutationFn: declineWingperson });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: getGetApiWingpeopleQueryKey() });

  const handleAccept = async (contactId: string) => {
    const result = await acceptMutation.mutateAsync(contactId).catch((err) => {
      toastError(err, "Couldn't accept invitation. Try again.");
      return null;
    });
    if (result == null) return;
    invalidate();
  };

  const handleDecline = async (contactId: string) => {
    const result = await declineMutation.mutateAsync(contactId).catch((err) => {
      toastError(err, "Couldn't decline invitation. Try again.");
      return null;
    });
    if (result == null) return;
    invalidate();
  };

  return (
    <ScrollView contentContainerClassName="pb-32">
      <View className="px-4 pt-2 pb-1 flex-row items-center justify-between">
        <Text className="font-serif text-ink" style={{ fontSize: 28, letterSpacing: -0.5 }}>
          Friends
        </Text>
        <Sprout size="sm" icon={<PlusIcon size={14} color={colors.white} />} onPress={onOpenInvite}>
          Invite
        </Sprout>
      </View>
      <Text className="px-4 pb-1 text-sm text-ink-dim">
        {wingingFor.length === 0
          ? 'Once a friend invites you, they appear here.'
          : `${wingingFor.length} ${wingingFor.length === 1 ? 'person trusts' : 'people trust'} your taste.`}
      </Text>

      {invitations.length > 0 && (
        <>
          <SectionHeader title={`Wants you to wing · ${invitations.length}`} />
          <View className="px-5" style={{ gap: 10 }}>
            {invitations.map((inv) => {
              const name = inv.dater?.chosenName ?? 'Unknown';
              return (
                <View
                  key={inv.id}
                  className="flex-row items-center bg-accent-muted rounded-2xl px-3.5 py-3"
                  style={{ gap: 12 }}
                >
                  <FaceAvatar name={name} size={42} />
                  <View className="flex-1">
                    <Text className="text-sm font-semibold text-ink">{name} invited you</Text>
                    <Text className="text-xs mt-0.5 text-ink-dim">Wing for them</Text>
                  </View>
                  <Sprout size="sm" variant="secondary" onPress={() => handleDecline(inv.id)}>
                    Decline
                  </Sprout>
                  <Sprout size="sm" onPress={() => handleAccept(inv.id)}>
                    Accept
                  </Sprout>
                </View>
              );
            })}
          </View>
        </>
      )}

      <SectionHeader title={`You wing for · ${wingingFor.length}`} />

      {wingingFor.length === 0 ? (
        <Text className="text-sm px-5 py-3 leading-5 text-ink-dim">
          No one has invited you to wing for them yet.
        </Text>
      ) : (
        <View className="px-4" style={{ gap: 10 }}>
          {wingingFor.map((wf) => {
            const name = wf.dater?.chosenName ?? 'Unknown';
            const sent = weeklyCounts[wf.id] ?? 0;
            return (
              <Pressable
                key={wf.id}
                onPress={() => navigation.navigate('FriendDetail', { daterId: wf.dater?.id ?? '' })}
                className="bg-white rounded-[18px] p-3.5"
                style={{
                  borderWidth: StyleSheet.hairlineWidth,
                  borderColor: colors.divider,
                }}
              >
                <View className="flex-row items-center" style={{ gap: 12 }}>
                  <FaceAvatar name={name} size={48} photoUri={wf.dater?.avatarUrl ?? null} />
                  <View className="flex-1">
                    <Text
                      className="font-serif text-ink"
                      style={{ fontSize: 20, letterSpacing: -0.3 }}
                    >
                      {name}
                    </Text>
                    <Text className="text-xs mt-0.5 text-ink-dim">
                      {sent} pick{sent !== 1 ? 's' : ''} this week
                    </Text>
                  </View>
                </View>
              </Pressable>
            );
          })}
        </View>
      )}
    </ScrollView>
  );
}

export default function FriendsScreen() {
  const [inviteVisible, setInviteVisible] = useState(false);

  return (
    <SafeAreaView className="flex-1 bg-page" edges={['top']}>
      <ScreenSuspense>
        <FriendsContent onOpenInvite={() => setInviteVisible(true)} />
      </ScreenSuspense>
      <InviteWingpersonSheet
        visible={inviteVisible}
        onClose={() => setInviteVisible(false)}
        variant="winger"
      />
    </SafeAreaView>
  );
}
