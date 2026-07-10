import { useState } from 'react';
import { ScrollView, Text, View } from '@/lib/tw';
import { Button } from '@/components/Button';
import { FaceAvatar } from '@/components/FaceAvatar';
import { StepHeader } from '@/features/onboarding/chrome';
import { InviteWingpersonSheet } from '@/features/wingpeople/InviteWingpersonSheet';

export function WingInviteStep({ onFinish }: { onFinish: () => void }) {
  // Both buttons open the same phone-collection sheet — a real, token-bound
  // invite link needs a Contact row to mint against, so "Share a link" can't
  // skip straight to Share.share() with a static URL. `deliveryMethod` only
  // changes how the resulting link is handed off.
  const [inviteVisible, setInviteVisible] = useState(false);
  const [deliveryMethod, setDeliveryMethod] = useState<'sms' | 'share'>('sms');

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
            <Button
              block
              size="md"
              onPress={() => {
                setDeliveryMethod('sms');
                setInviteVisible(true);
              }}
            >
              From contacts
            </Button>
            <Button
              block
              size="md"
              variant="secondary"
              onPress={() => {
                setDeliveryMethod('share');
                setInviteVisible(true);
              }}
            >
              Share a link
            </Button>
          </View>
        </View>
        <Text className="mt-3.5 text-xs text-foreground-subtle text-center leading-[18px]">
          You can do this later. Pear works either way.
        </Text>
      </ScrollView>
      <Button block size="md" onPress={onFinish}>
        Finish setup
      </Button>

      <InviteWingpersonSheet
        visible={inviteVisible}
        onClose={() => setInviteVisible(false)}
        deliveryMethod={deliveryMethod}
      />
    </View>
  );
}
