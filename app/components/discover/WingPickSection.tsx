import { useWindowDimensions } from 'react-native';

import { View, Text } from '@/lib/tw';
import { WingStack } from '@/components/ui/WingStack';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { PagedCarousel } from '@/components/ui/PagedCarousel';
import type { WingSuggestion } from '@/lib/api/generated/model';

function SuggestionCard({ suggestion, width }: { suggestion: WingSuggestion; width: number }) {
  const name = suggestion.wingerName ?? 'A friend';
  return (
    <View
      className="bg-leaf-soft flex-row gap-3 items-start"
      style={{
        width,
        borderWidth: 1,
        borderColor: 'rgba(90,140,58,0.15)',
        borderRadius: 14,
        padding: 12,
      }}
    >
      <FaceAvatar name={name} size={30} />
      <View className="flex-1 min-w-0">
        <Text
          className="text-primary"
          style={{
            fontSize: 10.5,
            fontWeight: '700',
            letterSpacing: 1.2,
            textTransform: 'uppercase',
            marginBottom: 3,
          }}
        >
          Hand-picked
        </Text>
        {suggestion.note != null ? (
          <Text className="text-ink" style={{ fontSize: 13, lineHeight: 18 }}>
            “{suggestion.note}”{' '}
            <Text className="text-ink-dim" style={{ fontStyle: 'italic' }}>
              — {name}
            </Text>
          </Text>
        ) : (
          <Text className="text-ink" style={{ fontSize: 13, lineHeight: 18 }}>
            <Text style={{ fontWeight: '700' }}>Hand-picked</Text> by {name}
          </Text>
        )}
      </View>
    </View>
  );
}

export function WingPickSection({
  suggestions,
  chosenName,
}: {
  suggestions: WingSuggestion[];
  chosenName: string;
}) {
  const { width: screenWidth } = useWindowDimensions();
  const cardWidth = screenWidth - 32; // matches the surrounding 16px card padding
  const GAP = 8;
  const pageWidth = cardWidth + GAP;

  if (suggestions.length === 0) return null;

  return (
    <View style={{ gap: 8 }}>
      <View className="flex-row items-center gap-2">
        <WingStack items={suggestions.map((s) => ({ name: s.wingerName ?? 'A friend' }))} size={22} />
        <Text className="text-ink-dim" style={{ fontSize: 12.5, fontWeight: '500' }}>
          Hand-picked · {suggestions.length} {suggestions.length === 1 ? 'friend suggests' : 'friends suggest'}{' '}
          {chosenName}
        </Text>
      </View>

      {suggestions.length === 1 ? (
        <SuggestionCard suggestion={suggestions[0]} width={cardWidth} />
      ) : (
        <PagedCarousel pageCount={suggestions.length} pageWidth={pageWidth} contentContainerStyle={{ gap: GAP }}>
          {suggestions.map((s, i) => (
            <SuggestionCard key={s.wingerId ?? i} suggestion={s} width={cardWidth} />
          ))}
        </PagedCarousel>
      )}
    </View>
  );
}
