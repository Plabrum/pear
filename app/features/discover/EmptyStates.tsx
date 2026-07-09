import { View, Text } from '@/lib/tw';
import { Card } from '@/components/Card';
import { Sprout } from '@/components/Sprout';
import { PearMark } from '@/components/PearMark';

// Shared dashed paper panel for the discover empty states.
function EmptyCard({ children }: { children: React.ReactNode }) {
  return (
    <Card
      className="flex-1 rounded-[22px] border-dashed items-center justify-center"
      style={{ padding: 32, gap: 16 }}
    >
      {children}
    </Card>
  );
}

export function FilterEmptyState({ onClear }: { onClear: () => void }) {
  return (
    <EmptyCard>
      <Text
        className="text-ink"
        style={{ fontFamily: 'DMSerifDisplay', fontSize: 24, lineHeight: 26, letterSpacing: -0.4 }}
      >
        Empty basket.
      </Text>
      <Text
        className="text-ink-mid"
        style={{ fontSize: 14, lineHeight: 21, textAlign: 'center', maxWidth: 280 }}
      >
        No one in your deck matches every filter you have on right now. Try fewer.
      </Text>
      <Sprout variant="secondary" onPress={onClear}>
        Clear filters
      </Sprout>
    </EmptyCard>
  );
}

export function WingEmptyState({ onInvite }: { onInvite: () => void }) {
  return (
    <EmptyCard>
      <View
        className="bg-leaf-soft items-center justify-center"
        style={{ width: 96, height: 96, borderRadius: 48 }}
      >
        <PearMark size={56} />
      </View>
      <View className="items-center">
        <Text
          className="text-ink"
          style={{
            fontFamily: 'DMSerifDisplay',
            fontSize: 26,
            lineHeight: 28,
            letterSpacing: -0.4,
            textAlign: 'center',
          }}
        >
          A pear takes two.
        </Text>
        <Text
          className="text-ink-mid"
          style={{
            fontSize: 14,
            lineHeight: 21,
            textAlign: 'center',
            marginTop: 10,
            maxWidth: 280,
          }}
        >
          Hand-picked profiles come from friends who know you. Invite someone to start scouting.
        </Text>
      </View>
      <View style={{ width: '100%', maxWidth: 240, gap: 8 }}>
        <Sprout block onPress={onInvite}>
          Invite a wingperson
        </Sprout>
      </View>
    </EmptyCard>
  );
}

export function NoMoreProfilesEmptyState() {
  return (
    <EmptyCard>
      <Text
        className="text-ink"
        style={{ fontFamily: 'DMSerifDisplay', fontSize: 24, lineHeight: 26, letterSpacing: -0.4 }}
      >
        All caught up.
      </Text>
      <Text
        className="text-ink-mid"
        style={{ fontSize: 14, lineHeight: 21, textAlign: 'center', maxWidth: 280 }}
      >
        You{"'"}ve seen everyone nearby for now. New profiles appear as people join.
      </Text>
    </EmptyCard>
  );
}
