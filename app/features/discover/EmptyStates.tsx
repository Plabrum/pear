import { View, Text } from '@/lib/tw';
import { Button } from '@/components/Button';
import { PearMark } from '@/components/PearMark';
import { EmptyCard } from '@/components/EmptyCard';

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
      <Button variant="secondary" onPress={onClear}>
        Clear filters
      </Button>
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
        <Button block onPress={onInvite}>
          Invite a wingperson
        </Button>
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
