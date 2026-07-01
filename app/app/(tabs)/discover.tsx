import React, { Suspense, useCallback, useState } from 'react';
import { Dimensions, Platform, StyleSheet } from 'react-native';
import PulseSpinner from '@/components/ui/PulseSpinner';
import { router } from 'expo-router';
import { useForm } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner-native';
import Animated, {
  Extrapolation,
  interpolate,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
  type SharedValue,
} from 'react-native-reanimated';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';

import {
  Modal,
  ModalView,
  View,
  Text,
  ScrollView,
  SafeAreaView,
  Pressable,
  TextInput,
} from '@/lib/tw';
import { useAuth } from '@/context/auth';
import { useDiscover, type PoolFetcher, type LikeResult } from '@/hooks/use-discover';
import type { Enums } from '@/types/database';
import { getApiDiscover, useGetApiDiscoverSuspense } from '@/lib/api/generated/discover/discover';
import { useGetApiLikesYouCountSuspense } from '@/lib/api/generated/likes-you/likes-you';
import type { DiscoverProfile, WingingForRow } from '@/lib/api/generated/model';
import {
  useGetApiDatingProfilesMeSuspense,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { reportProfile, updateDatingProfile } from '@/lib/api/actions';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import { LargeHeader } from '@/components/ui/LargeHeader';
import { Pill } from '@/components/ui/Pill';
import { Sprout } from '@/components/ui/Sprout';
import { WingStack } from '@/components/ui/WingStack';
import { PearMark } from '@/components/ui/PearMark';
import { ForwardSheet } from '@/components/ui/ForwardSheet';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { cardButtonShadow } from '@/lib/styles';

const PAGE_SIZE = 20;
const SWIPE_THRESHOLD = 110;
const SCREEN_WIDTH = Dimensions.get('window').width;

const LEAF = '#5A8C3A';
const LEAF_SOFT = '#E5EFD8';
const INK = '#1F1B16';
const INK_MUTED = '#4A4338';
const INK_SUBTLE = '#8B8170';
const PAPER = '#FBF8F1';
const LINE = 'rgba(31,27,22,0.10)';
const PASS_RED = '#C44';

type Filter = 'likes' | 'handpicked';

// ── DiscoverPausedScreen ──────────────────────────────────────────────────────

function DiscoverPausedScreen({
  status,
  datingProfileId,
  onResume,
}: {
  status: Exclude<Enums<'dating_status'>, 'open'>;
  datingProfileId: string;
  onResume: () => void;
}) {
  const {
    handleSubmit,
    formState: { isSubmitting },
  } = useForm();

  if (status === 'winging') {
    return (
      <SafeAreaView className="flex-1 bg-background">
        <LargeHeader title="Discover" />
        <View className="flex-1 justify-center items-center p-6">
          <Text className="text-2xl font-bold font-serif text-foreground text-center">
            Nothing to see here...
          </Text>
          <Text className="text-sm text-foreground-muted text-center mt-2 leading-[22px]">
            you{"'"}re just winging!
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  async function resume() {
    try {
      await updateDatingProfile(datingProfileId, { datingStatus: 'open' });
    } catch {
      toast.error('Something went wrong. Please try again.');
      return;
    }
    onResume();
  }

  return (
    <SafeAreaView className="flex-1 bg-background">
      <LargeHeader title="Discover" />
      <View className="flex-1 justify-center items-center p-6 gap-4">
        <Text className="text-2xl font-bold font-serif text-foreground text-center">
          You{"'"}re on a break
        </Text>
        <Text className="text-sm text-foreground-muted text-center leading-[22px]">
          Your profile is hidden while you{"'"}re on a break. Take all the time you need.
        </Text>
        <Sprout onPress={handleSubmit(resume)} loading={isSubmitting}>
          Resume Discover
        </Sprout>
      </View>
    </SafeAreaView>
  );
}

// ── DiscoverFilters ───────────────────────────────────────────────────────────

type FilterDef = {
  key: Filter;
  label: string;
  tone: 'ink' | 'leaf';
  icon: (color: string) => React.ReactElement;
};

const FILTERS: FilterDef[] = [
  {
    key: 'likes',
    label: 'Likes you',
    tone: 'ink',
    icon: (color) => <Ionicons name="heart" size={12} color={color} />,
  },
  {
    key: 'handpicked',
    label: 'Hand-picked',
    tone: 'leaf',
    icon: (color) => <PearMark size={13} color={color} variant="flat" />,
  },
];

function DiscoverFilters({
  active,
  onToggle,
  onClearAll,
  counts,
}: {
  active: Filter[];
  onToggle: (key: Filter) => void;
  onClearAll: () => void;
  counts: Partial<Record<Filter, number>>;
}) {
  return (
    <View className="flex-row items-center flex-wrap px-4 pt-1 pb-3 gap-2">
      <Pressable onPress={onClearAll} disabled={active.length === 0}>
        <Text className="text-[13px] text-foreground-muted font-medium mr-1">For you</Text>
      </Pressable>
      <Text className="text-foreground-subtle text-xs">·</Text>
      {FILTERS.map((f) => {
        const on = active.includes(f.key);
        const activeBg = f.tone === 'leaf' ? LEAF : INK;
        const activeFg = PAPER;
        const fg = on ? activeFg : INK;
        const count = counts[f.key];
        return (
          <Pressable
            key={f.key}
            onPress={() => onToggle(f.key)}
            className="flex-row items-center justify-center"
            style={{
              height: 32,
              paddingLeft: 8,
              paddingRight: 12,
              borderRadius: 18,
              borderWidth: 1,
              borderColor: on ? activeBg : LINE,
              backgroundColor: on ? activeBg : PAPER,
              gap: 5,
            }}
          >
            {f.icon(fg)}
            <Text style={{ color: fg, fontSize: 12.5, fontWeight: '600' }}>{f.label}</Text>
            {count != null && (
              <View
                style={{
                  backgroundColor: on ? 'rgba(255,255,255,0.22)' : '#EDE6D6',
                  borderRadius: 8,
                  height: 16,
                  minWidth: 16,
                  paddingHorizontal: 6,
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginLeft: 2,
                }}
              >
                <Text
                  style={{
                    color: on ? activeFg : INK_SUBTLE,
                    fontSize: 10.5,
                    fontWeight: '700',
                  }}
                >
                  {count}
                </Text>
              </View>
            )}
          </Pressable>
        );
      })}
    </View>
  );
}

// ── WingCredential ────────────────────────────────────────────────────────────

function WingCredential({ suggesterName, note }: { suggesterName: string; note: string | null }) {
  return (
    <View
      style={{
        backgroundColor: LEAF_SOFT,
        borderWidth: 1,
        borderColor: 'rgba(90,140,58,0.15)',
        borderRadius: 14,
        padding: 12,
      }}
      className="flex-row gap-3 items-start"
    >
      <WingStack items={[{ name: suggesterName }]} size={30} />
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
        {note != null ? (
          <Text className="text-ink" style={{ fontSize: 13, lineHeight: 18 }}>
            “{note}”{' '}
            <Text className="text-ink-dim" style={{ fontStyle: 'italic' }}>
              — {suggesterName}
            </Text>
          </Text>
        ) : (
          <Text className="text-ink" style={{ fontSize: 13, lineHeight: 18 }}>
            <Text style={{ fontWeight: '700' }}>Hand-picked</Text> by {suggesterName}
          </Text>
        )}
      </View>
    </View>
  );
}

// ── Stamp ─────────────────────────────────────────────────────────────────────

function PassStamp({ swipeX }: { swipeX: SharedValue<number> }) {
  const style = useAnimatedStyle(() => ({
    opacity: interpolate(swipeX.value, [-SWIPE_THRESHOLD, -20, 0], [1, 0, 0], Extrapolation.CLAMP),
  }));
  return (
    <Animated.View
      style={[
        {
          position: 'absolute',
          top: 24,
          right: 18,
          transform: [{ rotate: '14deg' }],
          borderWidth: 3,
          borderColor: PASS_RED,
          paddingVertical: 4,
          paddingHorizontal: 12,
          borderRadius: 8,
          backgroundColor: 'rgba(255,255,255,0.85)',
        },
        style,
      ]}
    >
      <Text style={{ color: PASS_RED, fontSize: 18, fontWeight: '700', letterSpacing: 2 }}>
        PASS
      </Text>
    </Animated.View>
  );
}

function LikeStamp({ swipeX }: { swipeX: SharedValue<number> }) {
  const style = useAnimatedStyle(() => ({
    opacity: interpolate(swipeX.value, [0, 20, SWIPE_THRESHOLD], [0, 0, 1], Extrapolation.CLAMP),
  }));
  return (
    <Animated.View
      style={[
        {
          position: 'absolute',
          top: 24,
          left: 18,
          transform: [{ rotate: '-14deg' }],
          borderWidth: 3,
          borderColor: LEAF,
          paddingVertical: 4,
          paddingHorizontal: 12,
          borderRadius: 8,
          backgroundColor: 'rgba(255,255,255,0.85)',
        },
        style,
      ]}
    >
      <Text className="text-primary" style={{ fontSize: 18, fontWeight: '700', letterSpacing: 2 }}>
        LIKE
      </Text>
    </Animated.View>
  );
}

// ── DiscoverCard ──────────────────────────────────────────────────────────────

type ReportStep = 'confirm' | 'reason';

function DiscoverCard({
  card,
  onLike,
  onPass,
  onReport,
  wingingFor,
}: {
  card: DiscoverProfile;
  onLike: () => void;
  onPass: () => void;
  onReport: (reason: string) => Promise<void>;
  wingingFor: WingingForRow[];
}) {
  const swipeX = useSharedValue(0);
  const [photoIndex, setPhotoIndex] = useState(0);
  const [reportStep, setReportStep] = useState<ReportStep | null>(null);
  const [reportReason, setReportReason] = useState('');
  const [reporting, setReporting] = useState(false);
  const [forwardOpen, setForwardOpen] = useState(false);
  const photos = card.photos;

  const finishSwipe = useCallback(
    (direction: 'like' | 'pass') => {
      swipeX.value = withTiming(0, { duration: 0 });
      if (direction === 'like') onLike();
      else onPass();
    },
    [swipeX, onLike, onPass]
  );

  const pan = Gesture.Pan()
    .activeOffsetX([-10, 10])
    .onUpdate((e) => {
      swipeX.value = e.translationX;
    })
    .onEnd((e) => {
      if (e.translationX > SWIPE_THRESHOLD) {
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

  async function submitReport() {
    if (!reportReason.trim() || reporting) return;
    setReporting(true);
    try {
      await onReport(reportReason.trim());
      setReportStep(null);
      setReportReason('');
    } catch {
      toast.error("Couldn't send report. Try again.");
    } finally {
      setReporting(false);
    }
  }

  return (
    <>
      <Modal
        visible={reportStep != null}
        transparent
        animationType="fade"
        onRequestClose={() => setReportStep(null)}
      >
        <ModalView
          backgroundColor="rgba(0,0,0,0.5)"
          style={{ justifyContent: 'center', alignItems: 'center', padding: 24 }}
        >
          <View
            style={{
              backgroundColor: PAPER,
              borderRadius: 22,
              padding: 24,
              width: '100%',
              maxWidth: 360,
              gap: 16,
            }}
          >
            {reportStep === 'confirm' ? (
              <>
                <View style={{ gap: 6 }}>
                  <Text style={{ fontFamily: 'DMSerifDisplay', fontSize: 22, color: INK }}>
                    Report profile?
                  </Text>
                  <Text style={{ fontSize: 14, color: INK_MUTED, lineHeight: 20 }}>
                    Something feel off? Let us know and we&apos;ll look into it.
                  </Text>
                </View>
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <Pressable
                    onPress={() => setReportStep(null)}
                    style={{
                      flex: 1,
                      paddingVertical: 13,
                      borderRadius: 14,
                      borderWidth: 1,
                      borderColor: LINE,
                      alignItems: 'center',
                    }}
                  >
                    <Text style={{ fontSize: 15, fontWeight: '600', color: INK_MUTED }}>
                      No, cancel
                    </Text>
                  </Pressable>
                  <Pressable
                    onPress={() => setReportStep('reason')}
                    style={{
                      flex: 1,
                      paddingVertical: 13,
                      borderRadius: 14,
                      backgroundColor: PASS_RED,
                      alignItems: 'center',
                    }}
                  >
                    <Text style={{ fontSize: 15, fontWeight: '600', color: PAPER }}>
                      Yes, report
                    </Text>
                  </Pressable>
                </View>
              </>
            ) : (
              <>
                <View style={{ gap: 6 }}>
                  <Text style={{ fontFamily: 'DMSerifDisplay', fontSize: 22, color: INK }}>
                    What&apos;s the issue?
                  </Text>
                  <Text style={{ fontSize: 14, color: INK_MUTED, lineHeight: 20 }}>
                    Describe the problem so we can review it.
                  </Text>
                </View>
                <TextInput
                  value={reportReason}
                  onChangeText={setReportReason}
                  placeholder="Describe the issue…"
                  placeholderTextColor={INK_SUBTLE}
                  multiline
                  maxLength={500}
                  style={{
                    backgroundColor: 'white',
                    borderWidth: 1,
                    borderColor: LINE,
                    borderRadius: 14,
                    padding: 14,
                    fontSize: 14,
                    color: INK,
                    minHeight: 100,
                    textAlignVertical: 'top',
                  }}
                />
                <View style={{ flexDirection: 'row', gap: 10 }}>
                  <Pressable
                    onPress={() => {
                      setReportStep(null);
                      setReportReason('');
                    }}
                    style={{
                      flex: 1,
                      paddingVertical: 13,
                      borderRadius: 14,
                      borderWidth: 1,
                      borderColor: LINE,
                      alignItems: 'center',
                    }}
                  >
                    <Text style={{ fontSize: 15, fontWeight: '600', color: INK_MUTED }}>
                      Cancel
                    </Text>
                  </Pressable>
                  <Pressable
                    onPress={submitReport}
                    disabled={!reportReason.trim() || reporting}
                    style={{
                      flex: 1,
                      paddingVertical: 13,
                      borderRadius: 14,
                      backgroundColor: PASS_RED,
                      alignItems: 'center',
                      opacity: !reportReason.trim() || reporting ? 0.4 : 1,
                    }}
                  >
                    <Text style={{ fontSize: 15, fontWeight: '600', color: PAPER }}>
                      {reporting ? 'Sending…' : 'Send'}
                    </Text>
                  </Pressable>
                </View>
              </>
            )}
          </View>
        </ModalView>
      </Modal>
      {wingingFor.length > 0 && (
        <ForwardSheet
          visible={forwardOpen}
          recipientId={card.userId}
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
              backgroundColor: PAPER,
              borderWidth: 1,
              borderColor: LINE,
              ...Platform.select({
                ios: {
                  shadowColor: '#000',
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
                source={{ uri: photos[photoIndex] }}
                style={StyleSheet.absoluteFillObject}
                contentFit="cover"
                transition={200}
              />
            ) : (
              <View style={[StyleSheet.absoluteFillObject, { backgroundColor: '#ebebf0' }]} />
            )}

            {/* Tap zones for photo navigation — sit above photo, below stamps */}
            <View
              style={[StyleSheet.absoluteFillObject, { flexDirection: 'row' }]}
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
              onPress={() => setReportStep('confirm')}
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
              {card.wingNote != null && card.suggesterName != null && (
                <WingCredential suggesterName={card.suggesterName} note={card.wingNote} />
              )}
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
                    backgroundColor: PAPER,
                    borderWidth: 1,
                    borderColor: LINE,
                    alignItems: 'center',
                    justifyContent: 'center',
                  },
                  cardButtonShadow,
                ]}
              >
                <Ionicons name="close" size={24} color={INK_MUTED} />
              </Pressable>
              <Pressable
                onPress={onLike}
                style={[
                  {
                    width: 60,
                    height: 60,
                    borderRadius: 30,
                    backgroundColor: LEAF,
                    alignItems: 'center',
                    justifyContent: 'center',
                  },
                  cardButtonShadow,
                ]}
              >
                <Ionicons name="heart" size={24} color={PAPER} />
              </Pressable>
            </View>
          </View>
        </Animated.View>
      </GestureDetector>
    </>
  );
}

// ── MatchOverlay ──────────────────────────────────────────────────────────────

function MatchOverlay({
  card,
  onClose,
  onMessage,
}: {
  card: DiscoverProfile;
  onClose: () => void;
  onMessage: () => void;
}) {
  return (
    <View
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 50,
        backgroundColor: '#F5E9D9',
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: 28,
      }}
    >
      <View style={{ position: 'absolute', top: 56, right: 20 }}>
        <Pressable
          onPress={onClose}
          style={{
            width: 38,
            height: 38,
            borderRadius: 19,
            backgroundColor: PAPER,
            borderWidth: 1,
            borderColor: LINE,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Ionicons name="close" size={18} color={INK} />
        </Pressable>
      </View>

      <Text
        className="text-primary"
        style={{
          fontSize: 11,
          letterSpacing: 2,
          textTransform: 'uppercase',
          marginBottom: 8,
          fontWeight: '600',
        }}
      >
        Mutual taste detected
      </Text>
      <Text
        className="text-ink"
        style={{
          fontFamily: 'DMSerifDisplay',
          fontSize: 56,
          lineHeight: 60,
          letterSpacing: -1.5,
          textAlign: 'center',
        }}
      >
        It’s a{' '}
        <Text className="text-primary" style={{ fontStyle: 'italic' }}>
          pear
        </Text>
        .
      </Text>

      <View style={{ flexDirection: 'row', marginTop: 36, marginBottom: 20 }}>
        <View
          style={{
            width: 118,
            height: 152,
            borderRadius: 20,
            overflow: 'hidden',
            transform: [{ rotate: '-4deg' }],
            borderWidth: 3,
            borderColor: PAPER,
            backgroundColor: '#ebebf0',
          }}
        >
          <View style={[StyleSheet.absoluteFillObject, { backgroundColor: '#D9C9B3' }]} />
        </View>
        <View
          style={{
            width: 118,
            height: 152,
            borderRadius: 20,
            overflow: 'hidden',
            transform: [{ rotate: '4deg' }, { translateX: -14 }],
            borderWidth: 3,
            borderColor: PAPER,
            backgroundColor: '#ebebf0',
          }}
        >
          {card.photos[0] ? (
            <Image
              source={{ uri: card.photos[0] }}
              style={StyleSheet.absoluteFillObject}
              contentFit="cover"
            />
          ) : (
            <View style={[StyleSheet.absoluteFillObject, { backgroundColor: '#C9B8A0' }]} />
          )}
        </View>
      </View>

      <Text
        className="text-ink-mid"
        style={{
          fontSize: 15,
          textAlign: 'center',
          maxWidth: 280,
          lineHeight: 22,
          marginBottom: 24,
        }}
      >
        You and {card.chosenName} both swiped right.
        {card.suggesterName != null ? ` ${card.suggesterName} called it.` : ''}
      </Text>

      <View style={{ width: '100%', maxWidth: 320, gap: 10 }}>
        <Sprout block size="lg" onPress={onMessage}>
          Send a message
        </Sprout>
        <Sprout block size="lg" variant="secondary" onPress={onClose}>
          Keep swiping
        </Sprout>
      </View>
    </View>
  );
}

// ── Empty states ──────────────────────────────────────────────────────────────

function FilterEmptyState({ onClear }: { onClear: () => void }) {
  return (
    <View
      style={{
        flex: 1,
        borderRadius: 22,
        backgroundColor: PAPER,
        borderWidth: 1,
        borderColor: LINE,
        borderStyle: 'dashed',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 32,
        gap: 16,
      }}
    >
      <Text
        className="text-ink"
        style={{
          fontFamily: 'DMSerifDisplay',
          fontSize: 24,
          lineHeight: 26,
          letterSpacing: -0.4,
        }}
      >
        Empty basket.
      </Text>
      <Text
        className="text-ink-mid"
        style={{
          fontSize: 14,
          lineHeight: 21,
          textAlign: 'center',
          maxWidth: 280,
        }}
      >
        No one in your deck matches every filter you have on right now. Try fewer.
      </Text>
      <Sprout variant="secondary" onPress={onClear}>
        Clear filters
      </Sprout>
    </View>
  );
}

function WingEmptyState({ onInvite }: { onInvite: () => void }) {
  return (
    <View
      style={{
        flex: 1,
        borderRadius: 22,
        backgroundColor: PAPER,
        borderWidth: 1,
        borderColor: LINE,
        borderStyle: 'dashed',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 32,
        gap: 16,
      }}
    >
      <View
        style={{
          width: 96,
          height: 96,
          borderRadius: 48,
          backgroundColor: LEAF_SOFT,
          alignItems: 'center',
          justifyContent: 'center',
        }}
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
    </View>
  );
}

function NoMoreProfilesEmptyState() {
  return (
    <View
      style={{
        flex: 1,
        borderRadius: 22,
        backgroundColor: PAPER,
        borderWidth: 1,
        borderColor: LINE,
        borderStyle: 'dashed',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 32,
        gap: 16,
      }}
    >
      <Text
        className="text-ink"
        style={{
          fontFamily: 'DMSerifDisplay',
          fontSize: 24,
          lineHeight: 26,
          letterSpacing: -0.4,
        }}
      >
        All caught up.
      </Text>
      <Text
        className="text-ink-mid"
        style={{
          fontSize: 14,
          lineHeight: 21,
          textAlign: 'center',
          maxWidth: 280,
        }}
      >
        You{"'"}ve seen everyone nearby for now. New profiles appear as people join.
      </Text>
    </View>
  );
}

// ── PoolView ──────────────────────────────────────────────────────────────────

type PoolViewProps = {
  userId: string;
  initialPool: DiscoverProfile[];
  fetchPool: PoolFetcher;
  emptyState: React.ReactNode;
  onDecrementLikes: ((recipientId: string) => void) | null;
  wingingFor: WingingForRow[];
};

function PoolView({
  userId,
  initialPool,
  fetchPool,
  emptyState,
  onDecrementLikes,
  wingingFor,
}: PoolViewProps) {
  const queryClient = useQueryClient();
  const { pool, index, like, pass } = useDiscover(fetchPool, userId, initialPool);
  const [matchCard, setMatchCard] = useState<DiscoverProfile | null>(null);
  const card = pool[index] ?? null;

  function invalidatePools(decidedCard: DiscoverProfile) {
    queryClient.invalidateQueries({ queryKey: ['/api/likes-you'], refetchType: 'none' });
    queryClient.invalidateQueries({ queryKey: ['/api/discover'], refetchType: 'none' });
    if (decidedCard.suggestedBy != null) {
      queryClient.invalidateQueries({ queryKey: ['/api/winger-tabs'], refetchType: 'none' });
    }
  }

  async function handleLike() {
    if (!card) return;
    const decidedCard = card;
    onDecrementLikes?.(decidedCard.userId);
    const result: LikeResult = await like();
    invalidatePools(decidedCard);
    if (result === 'match') {
      setMatchCard(decidedCard);
      queryClient.invalidateQueries({ queryKey: ['matches', userId] });
      queryClient.invalidateQueries({ queryKey: ['conversations', userId] });
    }
  }

  async function handlePass() {
    if (!card) return;
    const decidedCard = card;
    onDecrementLikes?.(decidedCard.userId);
    await pass();
    invalidatePools(decidedCard);
  }

  async function handleReport(reason: string) {
    if (!card) return;
    const reportedCard = card;
    onDecrementLikes?.(reportedCard.userId);
    await reportProfile({ recipientId: reportedCard.userId, reason });
    await pass();
    invalidatePools(reportedCard);
  }

  if (card == null) {
    return <View className="flex-1 px-3.5 pb-2">{emptyState}</View>;
  }

  return (
    <>
      <View className="flex-1 px-3.5 pb-2">
        <DiscoverCard
          card={card}
          onLike={handleLike}
          onPass={handlePass}
          onReport={handleReport}
          wingingFor={wingingFor}
        />
      </View>
      {matchCard && (
        <MatchOverlay
          card={matchCard}
          onClose={() => setMatchCard(null)}
          onMessage={() => setMatchCard(null)}
        />
      )}
    </>
  );
}

// ── Pool sources ──────────────────────────────────────────────────────────────

function LikesYouPool({
  userId,
  emptyState,
  onDecrementLikes,
  handPickedOnly,
  wingingFor,
}: {
  userId: string;
  emptyState: React.ReactNode;
  onDecrementLikes: ((recipientId: string) => void) | null;
  handPickedOnly: boolean;
  wingingFor: WingingForRow[];
}) {
  const { data: initialPool } = useGetApiDiscoverSuspense({
    pageSize: PAGE_SIZE,
    pageOffset: 0,
    likesYouOnly: true,
    ...(handPickedOnly && { wingerOnly: true }),
  });

  const fetchPool = useCallback<PoolFetcher>(
    (_uid, pageSize, offset) =>
      getApiDiscover({
        pageSize,
        pageOffset: offset,
        likesYouOnly: true,
        ...(handPickedOnly && { wingerOnly: true }),
      }),
    [handPickedOnly]
  );

  return (
    <PoolView
      userId={userId}
      initialPool={initialPool}
      fetchPool={fetchPool}
      emptyState={emptyState}
      onDecrementLikes={onDecrementLikes}
      wingingFor={wingingFor}
    />
  );
}

function DiscoverFeedPool({
  userId,
  emptyState,
  handPickedOnly,
  wingingFor,
}: {
  userId: string;
  emptyState: React.ReactNode;
  handPickedOnly: boolean;
  wingingFor: WingingForRow[];
}) {
  const { data: initialPool } = useGetApiDiscoverSuspense({
    pageSize: PAGE_SIZE,
    pageOffset: 0,
    ...(handPickedOnly && { wingerOnly: true }),
  });

  const fetchPool = useCallback<PoolFetcher>(
    (_uid, pageSize, offset) =>
      getApiDiscover({ pageSize, pageOffset: offset, ...(handPickedOnly && { wingerOnly: true }) }),
    [handPickedOnly]
  );

  return (
    <PoolView
      userId={userId}
      initialPool={initialPool}
      fetchPool={fetchPool}
      emptyState={emptyState}
      onDecrementLikes={null}
      wingingFor={wingingFor}
    />
  );
}

// ── DiscoverContent ───────────────────────────────────────────────────────────

function DiscoverContent({ userId }: { userId: string }) {
  const { data: likesYouCountResponse } = useGetApiLikesYouCountSuspense();
  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();
  const initialLikesYouCount = likesYouCountResponse.count;
  const wingingFor = wingpeopleData.wingingFor;
  const [activeFilters, setActiveFilters] = useState<Filter[]>([]);
  const [decidedLikesYou, setDecidedLikesYou] = useState<ReadonlySet<string>>(() => new Set());

  const likesYouCount = Math.max(0, initialLikesYouCount - decidedLikesYou.size);

  const toggleFilter = (key: Filter) => {
    setActiveFilters((prev) =>
      prev.includes(key) ? prev.filter((f) => f !== key) : [...prev, key]
    );
  };
  const clearFilters = () => setActiveFilters([]);

  const wantsLikes = activeFilters.includes('likes');
  const wantsHandPicked = activeFilters.includes('handpicked');
  const filterKey = `${wantsLikes ? 1 : 0}-${wantsHandPicked ? 1 : 0}`;

  const hasFilters = activeFilters.length > 0;

  const emptyState = !hasFilters ? (
    <NoMoreProfilesEmptyState />
  ) : wantsHandPicked && !wantsLikes ? (
    <WingEmptyState onInvite={() => router.push('/(tabs)/profile/wingpeople')} />
  ) : (
    <FilterEmptyState onClear={clearFilters} />
  );

  return (
    <SafeAreaView className="flex-1 bg-background">
      <LargeHeader title="Discover" />
      <DiscoverFilters
        active={activeFilters}
        onToggle={toggleFilter}
        onClearAll={clearFilters}
        counts={{ likes: likesYouCount }}
      />

      <Suspense
        fallback={
          <View className="flex-1 justify-center items-center p-6 gap-4">
            <PulseSpinner color={LEAF} />
          </View>
        }
      >
        {wantsLikes ? (
          <LikesYouPool
            key={`likes-${filterKey}`}
            userId={userId}
            emptyState={emptyState}
            onDecrementLikes={(recipientId: string) =>
              setDecidedLikesYou((prev) => {
                if (prev.has(recipientId)) return prev;
                const next = new Set(prev);
                next.add(recipientId);
                return next;
              })
            }
            handPickedOnly={wantsHandPicked}
            wingingFor={wingingFor}
          />
        ) : (
          <DiscoverFeedPool
            key={`feed-${filterKey}`}
            userId={userId}
            emptyState={emptyState}
            handPickedOnly={wantsHandPicked}
            wingingFor={wingingFor}
          />
        )}
      </Suspense>
    </SafeAreaView>
  );
}

// ── DiscoverScreen ────────────────────────────────────────────────────────────

export default function DiscoverScreen() {
  const { userId } = useAuth();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  if (datingProfile?.datingStatus !== 'open') {
    const status =
      (datingProfile?.datingStatus as Exclude<Enums<'dating_status'>, 'open'>) ?? 'break';
    return (
      <DiscoverPausedScreen
        status={status}
        datingProfileId={datingProfile?.id ?? ''}
        onResume={() =>
          queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() })
        }
      />
    );
  }

  const prefKey = [
    datingProfile?.ageFrom,
    datingProfile?.ageTo,
    datingProfile?.interestedGender?.join(','),
    datingProfile?.religiousPreference ?? '',
  ].join('|');

  return (
    <ScreenSuspense>
      <DiscoverContent key={prefKey} userId={userId} />
    </ScreenSuspense>
  );
}
