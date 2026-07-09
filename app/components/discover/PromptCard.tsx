import { useWindowDimensions } from 'react-native';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { View, Text } from '@/lib/tw';
import { colors } from '@/constants/theme';
import type { DiscoverPrompt } from '@/lib/api/generated/model';
import { Card } from '@/components/ui/Card';
import { PagedCarousel } from '@/components/ui/PagedCarousel';

// A response has no attributed name (unlike WingPickSection's suggestions) — it's
// anonymous "a friend said this" commentary, so the avatar is a plain mark, not an
// initial derived from a name.
function AnonymousWingMark({ size = 26 }: { size?: number }) {
  return (
    <View
      className="bg-primary items-center justify-center"
      style={{ width: size, height: size, borderRadius: size / 2 }}
    >
      <Ionicons name="leaf" size={Math.round(size * 0.55)} color={colors.white} />
    </View>
  );
}

export function PromptCard({ prompt }: { prompt: DiscoverPrompt }) {
  const { width: screenWidth } = useWindowDimensions();
  const cardWidth = screenWidth - 32; // matches the surrounding Card's p-4 (16px) padding
  const pageCount = 1 + prompt.responses.length;

  return (
    <Card className="p-4" style={{ position: 'relative' }}>
      {/* Peek strip: a sliver of a stacked card behind, hinting at more responses */}
      {prompt.responses.length > 0 && (
        <View
          pointerEvents="none"
          style={{
            position: 'absolute',
            top: 6,
            left: 6,
            right: -6,
            bottom: -6,
            borderRadius: 16,
            backgroundColor: colors.leafSoft,
            zIndex: -1,
          }}
        />
      )}

      <PagedCarousel pageCount={pageCount} pageWidth={cardWidth} gap={12}>
        <View style={{ width: '100%' }}>
          <Text
            className="text-primary"
            style={{
              fontSize: 10.5,
              fontWeight: '700',
              letterSpacing: 1.2,
              textTransform: 'uppercase',
              marginBottom: 6,
            }}
          >
            {prompt.question}
          </Text>
          <Text className="text-ink" style={{ fontSize: 15, lineHeight: 21 }}>
            {prompt.answer}
          </Text>
        </View>

        {prompt.responses.map((response, i) => (
          <View key={i} style={{ width: '100%', gap: 8 }}>
            <AnonymousWingMark />
            <Text className="text-ink" style={{ fontSize: 14, lineHeight: 20, fontStyle: 'italic' }}>
              “{response.message}”
            </Text>
          </View>
        ))}
      </PagedCarousel>
    </Card>
  );
}
