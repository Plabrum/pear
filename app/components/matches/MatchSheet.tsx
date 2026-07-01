import PulseSpinner from '@/components/ui/PulseSpinner';
import { router } from 'expo-router';
import { Image } from 'expo-image';

import { View, Text } from '@/lib/tw';
import { Sheet } from '@/components/ui/Sheet';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import type { MatchSummary } from '@/lib/api/generated/model';
import { GradientBlock } from '@/components/ui/GradientBlock';
import { Pill } from '@/components/ui/Pill';
import { Sprout } from '@/components/ui/Sprout';
import { colors } from '@/constants/theme';
import { matchedAgo } from '@/lib/time';
import { SheetBody } from './SheetBody';

type MatchSheetProps = {
  match: MatchSummary | null;
  visible: boolean;
  onClose: () => void;
};

export function MatchSheet({ match, visible, onClose }: MatchSheetProps) {
  if (!match) return null;

  const { other } = match;
  const interests: string[] = other.interests ?? [];
  const name = other.chosenName ?? 'Someone';
  const subtitleParts = [matchedAgo(match.createdAt), other.city].filter(Boolean);

  return (
    <Sheet
      visible={visible}
      onClose={onClose}
      size="full"
      footer={
        <Sprout
          block
          size="lg"
          onPress={() => {
            onClose();
            router.push({
              pathname: '/(tabs)/messages/[matchId]',
              params: {
                matchId: match.matchId,
                otherName: other.chosenName ?? '',
                otherUserId: other.id,
              },
            } as never);
          }}
        >
          {match.hasMessages ? 'Open conversation' : 'Start conversation'}
        </Sprout>
      }
    >
      {/* Header: name + age + subtitle */}
      <View style={{ flexDirection: 'row', alignItems: 'baseline' }}>
        <Text
          style={{
            fontFamily: 'DMSerifDisplay',
            fontSize: 32,
            letterSpacing: -0.5,
            color: colors.ink,
          }}
          numberOfLines={1}
        >
          {name}
        </Text>
        {other.age != null && (
          <Text style={{ fontSize: 22, marginLeft: 8, fontWeight: '400', color: colors.inkMid }}>
            {other.age}
          </Text>
        )}
      </View>
      {subtitleParts.length > 0 && (
        <Text style={{ fontSize: 13, marginTop: 2, color: colors.inkDim }}>
          {subtitleParts.join(' · ')}
        </Text>
      )}

      {/* Photo */}
      <View
        style={{
          marginTop: 16,
          borderRadius: 22,
          overflow: 'hidden',
          aspectRatio: 4 / 5,
          backgroundColor: colors.white,
        }}
      >
        {other.firstPhoto ? (
          <Image
            source={{ uri: other.firstPhoto }}
            style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
            contentFit="cover"
            transition={200}
          />
        ) : (
          <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
            <GradientBlock name={name} radius={0} />
          </View>
        )}
      </View>

      {/* Bio + interests */}
      <View style={{ paddingTop: 20, gap: 16 }}>
        {other.bio != null && other.bio.length > 0 && (
          <Text style={{ fontSize: 15, lineHeight: 22, color: colors.inkMid }}>{other.bio}</Text>
        )}
        {interests.length > 0 && (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {interests.map((interest, i) => (
              <Pill key={`${interest}-${i}`} label={interest} tone="cream" />
            ))}
          </View>
        )}
      </View>

      {/* Wing note + prompts (lazy) */}
      {visible && (
        <ScreenSuspense
          fallback={
            <View style={{ paddingTop: 24, alignItems: 'center' }}>
              <PulseSpinner color={colors.leaf} />
            </View>
          }
        >
          <SheetBody match={match} />
        </ScreenSuspense>
      )}
    </Sheet>
  );
}
