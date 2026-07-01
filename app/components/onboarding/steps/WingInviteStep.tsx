import { useState } from 'react';
import { Share } from 'react-native';
import { ScrollView, Text, View } from '@/lib/tw';
import { Sprout } from '@/components/ui/Sprout';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { StepHeader } from '@/components/onboarding/chrome';
import { InviteWingpersonSheet } from '@/components/wingpeople/InviteWingpersonSheet';

export function WingInviteStep({ onFinish }: { onFinish: () => void }) {
  const [inviteVisible, setInviteVisible] = useState(false);

  async function shareLink() {
    try {
      await Share.share({
        message: 'Be my wingperson on Pear: https://usepear.app/invite',
      });
    } catch {
      // user cancelled
    }
  }

  return (
    <View className="flex-1">
      <ScrollView className="flex-1" contentContainerClassName="pb-4">
        <StepHeader
          kicker="Step 4 · Bring a friend"
          title="Invite a"
          accent="wingperson"
          sub="They'll see profiles you swipe on, and can hand-pick people for you."
        />
        <View className="mt-5 p-[18px] bg-surface rounded-[20px] border border-border">
          <View className="flex-row items-center justify-center mb-3.5" style={{ paddingLeft: 14 }}>
            <View>
              <FaceAvatar name="Priya" size={52} ring={2} />
            </View>
            <View style={{ marginLeft: -14 }}>
              <FaceAvatar name="Jordan" size={52} ring={2} />
            </View>
            <View style={{ marginLeft: -14 }}>
              <FaceAvatar name="Sasha" size={52} ring={2} />
            </View>
          </View>
          <Text className="text-[13px] text-foreground-muted text-center leading-[19px] mb-3">
            Pick people who <Text className="text-foreground font-semibold">actually know you</Text>
            . Quality {'>'} quantity.
          </Text>
          <View style={{ gap: 8 }}>
            <Sprout block size="md" onPress={() => setInviteVisible(true)}>
              From contacts
            </Sprout>
            <Sprout block size="md" variant="secondary" onPress={shareLink}>
              Share a link
            </Sprout>
          </View>
        </View>
        <Text className="mt-3.5 text-xs text-foreground-subtle text-center leading-[18px]">
          You can do this later. Pear works either way.
        </Text>
      </ScrollView>
      <Sprout block size="md" onPress={onFinish}>
        Finish setup
      </Sprout>

      <InviteWingpersonSheet
        visible={inviteVisible}
        onClose={() => setInviteVisible(false)}
      />
    </View>
  );
}
