import LinearGradient from 'react-native-linear-gradient';

import { View, Text, Pressable } from '@/lib/tw';
import type { MatchSummary } from '@/lib/api/generated/model';
import { GradientBlock } from '@/components/ui/GradientBlock';
import { CrossfadeImage } from '@/components/ui/CrossfadeImage';
import { cardButtonShadow } from '@/lib/styles';

type MatchCardProps = {
  match: MatchSummary;
  onPress: () => void;
};

export function MatchCard({ match, onPress }: MatchCardProps) {
  const { other, hasMessages } = match;
  const isNew = !hasMessages;
  const name = other.chosenName ?? 'Someone';

  return (
    <Pressable
      onPress={onPress}
      className="bg-surface"
      style={[
        {
          aspectRatio: 3 / 4,
          borderRadius: 18,
          overflow: 'hidden',
        },
        cardButtonShadow,
      ]}
    >
      {other.firstPhoto ? (
        <CrossfadeImage
          uri={other.firstPhoto}
          style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
          resizeMode="cover"
        />
      ) : (
        <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
          <GradientBlock name={name} radius={0} />
        </View>
      )}

      {/* Bottom gradient scrim */}
      <LinearGradient
        pointerEvents="none"
        colors={['transparent', 'rgba(0,0,0,0.7)']}
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: '55%',
        }}
      />

      {isNew && (
        <View
          className="bg-leaf"
          style={{
            position: 'absolute',
            top: 10,
            left: 10,
            paddingHorizontal: 8,
            paddingVertical: 3,
            borderRadius: 8,
          }}
        >
          <Text
            className="text-surface"
            style={{
              fontSize: 10,
              fontWeight: '700',
              letterSpacing: 1,
              textTransform: 'uppercase',
            }}
          >
            New
          </Text>
        </View>
      )}

      <View style={{ position: 'absolute', left: 12, right: 12, bottom: 10 }}>
        <View className="flex-row items-baseline">
          <Text
            className="text-surface"
            style={{
              fontFamily: 'DMSerifDisplay',
              fontSize: 19,
              letterSpacing: -0.3,
            }}
            numberOfLines={1}
          >
            {name}
          </Text>
          {other.age != null && (
            <Text style={{ fontSize: 15, color: 'rgba(255,255,255,0.85)', marginLeft: 6 }}>
              {other.age}
            </Text>
          )}
        </View>
      </View>
    </Pressable>
  );
}
