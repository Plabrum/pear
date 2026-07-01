import { useState } from 'react';
import { Pressable, SafeAreaView, Text, View } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { Sprout } from '@/components/ui/Sprout';
import { PearMark } from '@/components/ui/PearMark';
import type { Database } from '@/types/database';

type Role = Database['public']['Enums']['user_role'];

type CardProps = {
  selected: boolean;
  title: string;
  sub: string;
  body: string;
  illustration: React.ReactNode;
  onPress: () => void;
};

function RoleCard({ selected, title, sub, body, illustration, onPress }: CardProps) {
  return (
    <Pressable
      onPress={onPress}
      className={cn(
        'rounded-[24px] overflow-hidden bg-surface border-[1.5px]',
        selected ? 'border-primary' : 'border-border'
      )}
    >
      <View
        className={cn(
          'h-[92px] relative overflow-hidden',
          selected ? 'bg-primary-soft' : 'bg-surface-muted'
        )}
      >
        {illustration}
      </View>
      <View className="px-[18px] pt-[14px] pb-4">
        <View className="flex-row items-center justify-between mb-1">
          <Text
            className="font-serif text-foreground"
            style={{ fontSize: 26, lineHeight: 28, letterSpacing: -0.4 }}
          >
            {title}
          </Text>
          <View
            className={cn(
              'w-6 h-6 rounded-full items-center justify-center border-[1.5px]',
              selected ? 'bg-primary border-primary' : 'bg-transparent border-foreground-subtle'
            )}
          >
            {selected ? (
              <Text className="text-primary-foreground" style={{ fontSize: 13, lineHeight: 13 }}>
                ✓
              </Text>
            ) : null}
          </View>
        </View>
        <Text
          className="text-foreground-subtle uppercase"
          style={{ fontSize: 12, letterSpacing: 0.4, fontVariant: ['tabular-nums'] }}
        >
          {sub}
        </Text>
        <Text className="text-[13.5px] text-foreground-muted mt-2 leading-[19px]">{body}</Text>
      </View>
    </Pressable>
  );
}

function DaterIllustration() {
  return (
    <View className="absolute inset-0 items-end justify-center pr-[18px]">
      <View className="flex-row">
        <View style={{ transform: [{ rotate: '-6deg' }] }}>
          <PearMark size={64} />
        </View>
        <View style={{ transform: [{ rotate: '8deg' }, { translateX: -12 }, { translateY: 4 }] }}>
          <PearMark size={56} variant="flat" color="#A8C99B" />
        </View>
      </View>
    </View>
  );
}

function WingerIllustration() {
  return (
    <View className="absolute inset-0 items-end justify-center pr-[18px]">
      <View style={{ width: 130, height: 80 }}>
        <View
          style={{ position: 'absolute', top: 6, right: 60, transform: [{ rotate: '-10deg' }] }}
        >
          <PearMark size={48} variant="flat" color="#E8B4B4" />
        </View>
        <View style={{ position: 'absolute', top: -4, right: 14, transform: [{ rotate: '6deg' }] }}>
          <PearMark size={62} variant="flat" color="#A8C99B" />
        </View>
      </View>
    </View>
  );
}

type Props = { onNext: (role: Role) => void };

export default function RoleStep({ onNext }: Props) {
  const [selected, setSelected] = useState<Role | null>(null);

  return (
    <SafeAreaView className="flex-1 bg-background">
      <View className="flex-1 px-6 pt-16 pb-7">
        <View className="flex-1">
          <View className="flex-row items-center mb-[18px]" style={{ gap: 6 }}>
            {[1, 2, 3, 4].map((s) => (
              <View
                key={s}
                className={cn('flex-1 rounded-[2px]', s === 1 ? 'bg-primary' : 'bg-border')}
                style={{ height: 3 }}
              />
            ))}
          </View>
          <Text
            className="font-mono text-foreground-subtle uppercase mb-3"
            style={{ fontSize: 10.5, letterSpacing: 1.6 }}
          >
            Step 1 · The basics
          </Text>
          <Text
            className="font-serif text-foreground"
            style={{ fontSize: 28, lineHeight: 30, letterSpacing: -0.7 }}
          >
            How are you using Pear?
          </Text>
          <Text className="text-sm text-foreground-muted mt-2.5 leading-[21px]">
            You can always switch later.
          </Text>

          <View className="flex-col mt-[22px]" style={{ gap: 12 }}>
            <RoleCard
              selected={selected === 'dater'}
              title="I'm Dating"
              sub="Swipe · match · wing"
              body="Your wingpeople help curate. You stay in control of who you talk to."
              illustration={<DaterIllustration />}
              onPress={() => setSelected('dater')}
            />
            <RoleCard
              selected={selected === 'winger'}
              title="I'm Just Winging"
              sub="Help a friend"
              body="Suggest profiles, drop a note, and contribute to your friend's profile."
              illustration={<WingerIllustration />}
              onPress={() => setSelected('winger')}
            />
          </View>
        </View>

        <Sprout block size="md" disabled={!selected} onPress={() => selected && onNext(selected)}>
          Continue
        </Sprout>
      </View>
    </SafeAreaView>
  );
}
