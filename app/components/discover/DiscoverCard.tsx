import React, { useCallback, useState } from 'react';
import { Platform, StyleSheet } from 'react-native';
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';

import { View, Text, ScrollView, Pressable } from '@/lib/tw';
import { colors } from '@/constants/theme';
import type { SwipeProfile, WingingForRow } from '@/lib/api/generated/model';
import { Pill } from '@/components/ui/Pill';
import { ForwardSheet } from '@/components/ui/ForwardSheet';
import { useActionFormRenderer } from '@/hooks/actions/use-action-form-renderer';
import type { ActionDTO } from '@/lib/actions/types';
import { cardButtonShadow } from '@/lib/styles';

import { SWIPE_THRESHOLD, SCREEN_WIDTH } from './constants';
import { PassStamp, LikeStamp } from './Stamps';
import { WingPickSection } from './WingPickSection';
import { PromptCard } from './PromptCard';

// Report is an object action on the swiped DatingProfile; the form (registry)
// collects the reason, the deck hook records it against `card.profileId`.
const REPORT: ActionDTO = {
  action: 'dating_profile_swipe_actions__report',
  label: 'Report',
  action_group_type: 'dating_profile_swipe_actions',
};

export function DiscoverCard({
  card,
  onLike,
  onPass,
  onReport,
  wingingFor,
}: {
  card: SwipeProfile;
  onLike: () => void;
  onPass: () => void;
  onReport: (reason: string) => Promise<void>;
  wingingFor: WingingForRow[];
}) {
  const swipeX = useSharedValue(0);
  const [photoIndex, setPhotoIndex] = useState(0);
  const [reportOpen, setReportOpen] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [forwardOpen, setForwardOpen] = useState(false);
  const photos = card.photos;
  // The report form (confirm → reason) is pulled from the action registry.
  const renderReportForm = useActionFormRenderer();

  const finishSwipe = useCallback(
    (direction: 'like' | 'pass') => {
      // reanimated shared values are mutated through `.value` by design; the
      // React Compiler immutability rule can't model this and false-positives.
      // eslint-disable-next-line react-hooks/immutability
      swipeX.value = withTiming(0, { duration: 0 });
      if (direction === 'like') onLike();
      else onPass();
    },
    [swipeX, onLike, onPass]
  );

  const pan = Gesture.Pan()
    .activeOffsetX([-10, 10])
    .onUpdate((e) => {
      // reanimated shared value mutation — intended API (see note above).
      // eslint-disable-next-line react-hooks/immutability
      swipeX.value = e.translationX;
    })
    .onEnd((e) => {
      if (e.translationX > SWIPE_THRESHOLD) {
        // reanimated shared value mutation — intended API (see note above).
        // eslint-disable-next-line react-hooks/immutability
        swipeX.value = withTiming(SCREEN_WIDTH, { duration: 180 }, () => {
          runOnJS(finishSwipe)('like');
        });
      } else if (e.translationX < -SWIPE_THRESHOLD) {
        swipeX.value = withTiming(-SCREEN_WIDTH, { duration: 180 }, () => {
          runOnJS(finishSwipe)('pass');
        });
      } else {
        swipeX.value = withSpring(0, { damping: 18, stiffness: 200 });
      }
    });

  const cardStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: swipeX.value }, { rotate: `${swipeX.value * 0.04}deg` }],
  }));

  async function handleReportSubmit(reason: string) {
    setReporting(true);
    try {
      await onReport(reason);
      setReportOpen(false);
    } finally {
      setReporting(false);
    }
  }

  return (
    <>
      {reportOpen &&
        renderReportForm({
          action: REPORT,
          onSubmit: (body) => void handleReportSubmit((body.data?.reason ?? '') as string),
          onClose: () => setReportOpen(false),
          isSubmitting: reporting,
          isOpen: true,
          actionLabel: REPORT.label,
        })}
      {wingingFor.length > 0 && (
        <ForwardSheet
          visible={forwardOpen}
          recipientId={card.userId}
          recipientProfileId={card.profileId}
          recipientName={card.chosenName}
          wingingFor={wingingFor}
          onClose={() => setForwardOpen(false)}
        />
      )}
      <GestureDetector gesture={pan}>
        <Animated.View
          style={[
            {
              flex: 1,
              borderRadius: 22,
              overflow: 'hidden',
              backgroundColor: colors.white,
              borderWidth: 1,
              borderColor: colors.divider,
              ...Platform.select({
                ios: {
                  shadowColor: 'black',
                  shadowOffset: { width: 0, height: 12 },
                  shadowOpacity: 0.1,
                  shadowRadius: 24,
                },
                android: { elevation: 6 },
              }),
            },
            cardStyle,
          ]}
        >
          {/* Photo region */}
          <View style={{ flex: 6, position: 'relative' }}>
            {photos.length > 0 ? (
              <Image
                source={{ uri: photos[photoIndex].url }}
                style={StyleSheet.absoluteFill}
                contentFit="cover"
                transition={200}
              />
            ) : (
              <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.muted }]} />
            )}

            {/* Wing-pick badge — this photo was suggested by a friend, not self-uploaded */}
            {photos.length > 0 && photos[photoIndex].pickedByName != null && (
              <View
                pointerEvents="none"
                style={{
                  position: 'absolute',
                  top: 14,
                  left: 52,
                  right: 52,
                  flexDirection: 'row',
                  justifyContent: 'center',
                }}
              >
                <View
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 5,
                    paddingHorizontal: 10,
                    paddingVertical: 5,
                    borderRadius: 12,
                    backgroundColor: 'rgba(0,0,0,0.45)',
                  }}
                >
                  <View
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: 7,
                      backgroundColor: 'rgba(255,255,255,0.9)',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Text style={{ fontSize: 9, fontWeight: '700', color: colors.ink }}>
                      {(photos[photoIndex].pickedByName ?? '?').charAt(0).toUpperCase()}
                    </Text>
                  </View>
                  <Text style={{ fontSize: 11, fontWeight: '600', color: 'rgba(255,255,255,0.95)' }}>
                    {photos[photoIndex].pickedByName}&apos;s pick
                  </Text>
                </View>
              </View>
            )}

            {/* Tap zones for photo navigation — sit above photo, below stamps */}
            <View
              style={[StyleSheet.absoluteFill, { flexDirection: 'row' }]}
              pointerEvents="box-none"
            >
              <Pressable
                style={{ flex: 1 }}
                onPress={() => setPhotoIndex((i) => Math.max(0, i - 1))}
              />
              <Pressable
                style={{ flex: 1 }}
                onPress={() => setPhotoIndex((i) => Math.min(photos.length - 1, i + 1))}
              />
            </View>

            <PassStamp swipeX={swipeX} />
            <LikeStamp swipeX={swipeX} />

            {/* Photo indicator bars */}
            {photos.length > 1 && (
              <View
                style={{
                  position: 'absolute',
                  top: 10,
                  left: 16,
                  right: 16,
                  flexDirection: 'row',
                  gap: 4,
                }}
                pointerEvents="none"
              >
                {photos.map((_, i) => (
                  <View
                    key={i}
                    style={{
                      flex: 1,
                      height: 3,
                      borderRadius: 2,
                      backgroundColor:
                        i === photoIndex ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.4)',
                    }}
                  />
                ))}
              </View>
            )}

            {/* Forward icon */}
            {wingingFor.length > 0 && (
              <Pressable
                onPress={() => setForwardOpen(true)}
                hitSlop={8}
                style={{
                  position: 'absolute',
                  top: 14,
                  left: 14,
                  width: 30,
                  height: 30,
                  borderRadius: 15,
                  backgroundColor: 'rgba(0,0,0,0.35)',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Ionicons name="arrow-redo-outline" size={16} color="rgba(255,255,255,0.9)" />
              </Pressable>
            )}

            {/* Report icon */}
            <Pressable
              onPress={() => setReportOpen(true)}
              hitSlop={8}
              style={{
                position: 'absolute',
                top: 14,
                right: 14,
                width: 30,
                height: 30,
                borderRadius: 15,
                backgroundColor: 'rgba(0,0,0,0.35)',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Ionicons name="alert-circle-outline" size={18} color="rgba(255,255,255,0.9)" />
            </Pressable>

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

            <View style={{ position: 'absolute', left: 16, right: 16, bottom: 14 }}>
              <View className="flex-row items-baseline gap-2">
                <Text
                  className="text-surface"
                  style={{
                    fontFamily: 'DMSerifDisplay',
                    fontSize: 30,
                    letterSpacing: -0.5,
                  }}
                >
                  {card.chosenName}
                </Text>
                <Text style={{ fontSize: 22, color: 'rgba(255,255,255,0.9)' }}>{card.age}</Text>
              </View>
              {card.city != null && (
                <Text style={{ fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 4 }}>
                  {card.city}
                </Text>
              )}
            </View>
          </View>

          {/* Info region */}
          <View style={{ flex: 4 }}>
            <ScrollView
              className="flex-1"
              contentContainerStyle={{ padding: 16, paddingBottom: 84, gap: 10 }}
              showsVerticalScrollIndicator={false}
            >
              {card.suggestions.length > 0 && (
                <WingPickSection suggestions={card.suggestions} chosenName={card.chosenName} />
              )}
              {card.prompts.map((prompt, i) => (
                <PromptCard key={i} prompt={prompt} />
              ))}
              {card.bio != null && (
                <Text className="text-ink-mid" style={{ fontSize: 14, lineHeight: 20 }}>
                  {card.bio}
                </Text>
              )}
              {card.interests.length > 0 && (
                <View className="flex-row flex-wrap gap-1.5">
                  {card.interests.map((interest) => (
                    <Pill key={interest} label={interest} tone="cream" size="sm" />
                  ))}
                </View>
              )}
            </ScrollView>

            {/* Action buttons */}
            <View
              pointerEvents="box-none"
              style={{
                position: 'absolute',
                bottom: 14,
                left: 0,
                right: 0,
                flexDirection: 'row',
                justifyContent: 'center',
                alignItems: 'center',
                gap: 18,
              }}
            >
              <Pressable
                onPress={onPass}
                style={[
                  {
                    width: 60,
                    height: 60,
                    borderRadius: 30,
                    backgroundColor: colors.white,
                    borderWidth: 1,
                    borderColor: colors.divider,
                    alignItems: 'center',
                    justifyContent: 'center',
                  },
                  cardButtonShadow,
                ]}
              >
                <Ionicons name="close" size={24} color={colors.inkMid} />
              </Pressable>
              <Pressable
                onPress={onLike}
                style={[
                  {
                    width: 60,
                    height: 60,
                    borderRadius: 30,
                    backgroundColor: colors.leaf,
                    alignItems: 'center',
                    justifyContent: 'center',
                  },
                  cardButtonShadow,
                ]}
              >
                <Ionicons name="heart" size={24} color={colors.white} />
              </Pressable>
            </View>
          </View>
        </Animated.View>
      </GestureDetector>
    </>
  );
}
