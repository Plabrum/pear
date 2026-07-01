import { useState } from 'react';
import { FlatList, KeyboardAvoidingView, Modal, Platform } from 'react-native';
import PulseSpinner from '@/components/ui/PulseSpinner';
import { router } from 'expo-router';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';

import { LinearGradient } from 'expo-linear-gradient';

import { View, Text, Pressable, ScrollView, SafeAreaView } from '@/lib/tw';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import {
  useGetApiMatchesMatchIdSheetSuspense,
  getGetApiMatchesMatchIdSheetQueryKey,
  useGetApiMatchesSuspense,
} from '@/lib/api/generated/matches/matches';
import type { MatchSummary } from '@/lib/api/generated/model';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import { useActionFormRenderer } from '@/hooks/actions/use-action-form-renderer';
import type { ActionDTO } from '@/lib/actions/types';
import { LargeHeader } from '@/components/ui/LargeHeader';
import { GradientBlock } from '@/components/ui/GradientBlock';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { Pill } from '@/components/ui/Pill';
import { Sprout } from '@/components/ui/Sprout';
import { cardButtonShadow } from '@/lib/styles';

const LEAF = '#5A8C3A';
const LEAF_SOFT = '#E5EFD8';
const INK = '#1F1B16';
const PAPER = '#FBF8F1';

// The matched person's reply to a prompt — a top-level create on prompt_response_actions.
const ADD_RESPONSE: ActionDTO = {
  action: 'prompt_response_actions__create',
  label: 'Reply',
  action_group_type: 'prompt_response_actions',
};
const CREAM = '#F5F1E8';
const LINE = 'rgba(31,27,22,0.10)';

// ── Icons ─────────────────────────────────────────────────────────────────────

// ── Helpers ───────────────────────────────────────────────────────────────────

function matchedAgo(createdAt: string): string {
  const days = Math.max(
    0,
    Math.floor((Date.now() - new Date(createdAt.replace(' ', 'T')).getTime()) / 86400000)
  );
  if (days === 0) return 'matched today';
  if (days === 1) return 'matched 1 day ago';
  if (days < 30) return `matched ${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? 'matched 1 month ago' : `matched ${months} months ago`;
}

// ── MatchCard (grid cell) ─────────────────────────────────────────────────────

type MatchCardProps = {
  match: MatchSummary;
  onPress: () => void;
};

function MatchCard({ match, onPress }: MatchCardProps) {
  const { other, hasMessages } = match;
  const isNew = !hasMessages;
  const name = other.chosenName ?? 'Someone';

  return (
    <Pressable
      onPress={onPress}
      style={[
        {
          aspectRatio: 3 / 4,
          borderRadius: 18,
          overflow: 'hidden',
          backgroundColor: PAPER,
        },
        cardButtonShadow,
      ]}
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
          style={{
            position: 'absolute',
            top: 10,
            left: 10,
            backgroundColor: LEAF,
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

// ── PromptCard ────────────────────────────────────────────────────────────────

type PromptCardProps = {
  question: string | null;
  answer: string;
  sent: boolean;
  onOpen: () => void;
};

function PromptCard({ question, answer, sent, onOpen }: PromptCardProps) {
  return (
    <View
      style={{
        backgroundColor: PAPER,
        borderWidth: 1,
        borderColor: LINE,
        borderRadius: 18,
        padding: 14,
      }}
    >
      {question != null && (
        <Text
          className="text-ink-dim"
          style={{
            fontSize: 10.5,
            textTransform: 'uppercase',
            letterSpacing: 1.4,
            marginBottom: 4,
            fontWeight: '700',
          }}
        >
          {question}
        </Text>
      )}
      <Text
        className="text-ink"
        style={{
          fontFamily: 'DMSerifDisplay',
          fontSize: 19,
          lineHeight: 24,
          letterSpacing: -0.3,
        }}
      >
        “{answer}”
      </Text>

      <View style={{ marginTop: 10 }}>
        {sent ? (
          <View className="flex-row items-center gap-1.5">
            <Ionicons name="checkmark" size={14} color={LEAF} />
            <Text className="text-primary" style={{ fontSize: 12.5, fontWeight: '600' }}>
              Reply sent
            </Text>
          </View>
        ) : (
          <Pressable onPress={onOpen} hitSlop={6}>
            <Text className="text-primary" style={{ fontSize: 13, fontWeight: '600' }}>
              Reply to this prompt →
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

// ── SheetBody (lazy wing note + prompts) ──────────────────────────────────────

function SheetBody({ match }: { match: MatchSummary }) {
  const { data } = useGetApiMatchesMatchIdSheetSuspense(match.matchId);
  const { wingNote, prompts } = data;
  const [sentPrompts, setSentPrompts] = useState<ReadonlySet<string>>(() => new Set());
  const [respondingTo, setRespondingTo] = useState<{ id: string; question: string | null } | null>(
    null
  );

  // The prompt-response create tags (/prompt-responses, /profile-prompts) don't
  // cover this match's sheet, so refresh it explicitly via onInvalidate.
  const executor = useActionExecutor({
    actionGroup: 'prompt_response_actions',
    onInvalidate: (qc) => {
      void qc.invalidateQueries({ queryKey: getGetApiMatchesMatchIdSheetQueryKey(match.matchId) });
    },
  });
  // The prompt-response form is pulled from the action registry; objectData is the prompt.
  const renderResponseForm = useActionFormRenderer(respondingTo ?? undefined);

  return (
    <View style={{ paddingHorizontal: 20, gap: 16, paddingTop: 16 }}>
      {wingNote != null && (
        <View
          style={{
            backgroundColor: LEAF_SOFT,
            borderRadius: 16,
            padding: 14,
            flexDirection: 'row',
            gap: 10,
            alignItems: 'flex-start',
          }}
        >
          <FaceAvatar name={wingNote.winger?.chosenName ?? 'Wing'} size={28} />
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text
              className="text-primary"
              style={{
                fontSize: 11,
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
              }}
            >
              {wingNote.winger?.chosenName ?? 'Your wing'} says
            </Text>
            <Text className="text-ink" style={{ fontSize: 13, lineHeight: 18, marginTop: 2 }}>
              “{wingNote.note}”
            </Text>
          </View>
        </View>
      )}

      {prompts.map((prompt) => (
        <PromptCard
          key={prompt.id}
          question={prompt.template?.question ?? null}
          answer={prompt.answer}
          sent={sentPrompts.has(prompt.id)}
          onOpen={() =>
            setRespondingTo({ id: prompt.id, question: prompt.template?.question ?? null })
          }
        />
      ))}

      {respondingTo &&
        renderResponseForm({
          action: ADD_RESPONSE,
          onSubmit: (body) => {
            const promptId = respondingTo.id;
            // silent: the optimistic "Reply sent" tag is our feedback; executor still
            // invalidates the sheet + error-toasts.
            void executor
              .executeAction(ADD_RESPONSE, body, { silent: true })
              .then(() => setSentPrompts((prev) => new Set(prev).add(promptId)))
              .catch(() => {});
            setRespondingTo(null);
          },
          onClose: () => setRespondingTo(null),
          isSubmitting: executor.isExecuting,
          isOpen: true,
          actionLabel: ADD_RESPONSE.label,
        })}
    </View>
  );
}

// ── MatchSheet ────────────────────────────────────────────────────────────────

type MatchSheetProps = {
  match: MatchSummary | null;
  visible: boolean;
  onClose: () => void;
};

function MatchSheet({ match, visible, onClose }: MatchSheetProps) {
  if (!match) return null;

  const { other } = match;
  const interests: string[] = other.interests ?? [];
  const name = other.chosenName ?? 'Someone';
  const subtitleParts = [matchedAgo(match.createdAt), other.city].filter(Boolean);

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        style={{ flex: 1, backgroundColor: CREAM }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          className="flex-1"
          contentContainerStyle={{ paddingBottom: 24 }}
          keyboardShouldPersistTaps="handled"
        >
          {/* Handle bar */}
          <View
            style={{
              alignSelf: 'center',
              width: 40,
              height: 4,
              borderRadius: 2,
              backgroundColor: LINE,
              marginTop: 8,
              marginBottom: 12,
            }}
          />

          {/* Header row: name + age + subtitle, close button */}
          <View
            style={{
              paddingHorizontal: 20,
              paddingBottom: 16,
              flexDirection: 'row',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 12,
            }}
          >
            <View style={{ flex: 1, minWidth: 0 }}>
              <View className="flex-row items-baseline">
                <Text
                  className="text-ink"
                  style={{
                    fontFamily: 'DMSerifDisplay',
                    fontSize: 32,
                    letterSpacing: -0.5,
                  }}
                  numberOfLines={1}
                >
                  {name}
                </Text>
                {other.age != null && (
                  <Text
                    className="text-ink-mid"
                    style={{
                      fontSize: 22,
                      marginLeft: 8,
                      fontWeight: '400',
                    }}
                  >
                    {other.age}
                  </Text>
                )}
              </View>
              {subtitleParts.length > 0 && (
                <Text className="text-ink-dim" style={{ fontSize: 13, marginTop: 2 }}>
                  {subtitleParts.join(' · ')}
                </Text>
              )}
            </View>
            <Pressable
              onPress={onClose}
              hitSlop={12}
              style={{
                width: 32,
                height: 32,
                borderRadius: 16,
                backgroundColor: PAPER,
                borderWidth: 1,
                borderColor: LINE,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Ionicons name="close" size={16} color={INK} />
            </Pressable>
          </View>

          {/* Photo */}
          <View style={{ paddingHorizontal: 20 }}>
            <View
              style={{
                borderRadius: 22,
                overflow: 'hidden',
                aspectRatio: 4 / 5,
                backgroundColor: PAPER,
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
          </View>

          {/* Bio + interests */}
          <View style={{ paddingHorizontal: 20, paddingTop: 20, gap: 16 }}>
            {other.bio != null && other.bio.length > 0 && (
              <Text className="text-ink-mid" style={{ fontSize: 15, lineHeight: 22 }}>
                {other.bio}
              </Text>
            )}
            {interests.length > 0 && (
              <View className="flex-row flex-wrap gap-1.5">
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
                  <PulseSpinner color={LEAF} />
                </View>
              }
            >
              <SheetBody match={match} />
            </ScreenSuspense>
          )}
        </ScrollView>

        {/* Sticky CTA */}
        <View
          style={{
            paddingHorizontal: 16,
            paddingTop: 12,
            paddingBottom: 24,
            borderTopWidth: 1,
            borderTopColor: LINE,
            backgroundColor: PAPER,
          }}
        >
          <Sprout
            block
            size="lg"
            onPress={() => {
              onClose();
              router.push(`/(tabs)/messages/${match.matchId}` as never);
            }}
          >
            {match.hasMessages ? 'Open conversation' : 'Start conversation'}
          </Sprout>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ── MatchesList ───────────────────────────────────────────────────────────────

function MatchesList() {
  const { data: matches, refetch, isRefetching } = useGetApiMatchesSuspense();
  const [selectedMatch, setSelectedMatch] = useState<MatchSummary | null>(null);
  const newCount = matches.filter((m) => !m.hasMessages).length;

  return (
    <SafeAreaView className="flex-1 bg-background">
      <FlatList
        data={matches}
        keyExtractor={(item) => item.matchId}
        numColumns={2}
        columnWrapperStyle={{ gap: 12 }}
        contentContainerStyle={{ padding: 16, paddingBottom: 32, gap: 12 }}
        onRefresh={refetch}
        refreshing={isRefetching}
        ListHeaderComponent={
          <View style={{ marginHorizontal: -16, marginTop: -16, marginBottom: 4 }}>
            <LargeHeader
              title="Matches"
              right={
                newCount > 0 ? <Pill tone="leaf" size="sm" label={`${newCount} new`} /> : undefined
              }
            />
            <View style={{ paddingHorizontal: 20, paddingBottom: 8 }}>
              <Text className="text-ink-dim" style={{ fontSize: 13 }}>
                People who said yes. Pick one to nudge.
              </Text>
            </View>
          </View>
        }
        ListEmptyComponent={
          <View className="flex-1 items-center justify-center p-8">
            <Text
              className="text-ink"
              style={{
                fontFamily: 'DMSerifDisplay',
                fontSize: 22,
                letterSpacing: -0.4,
                textAlign: 'center',
              }}
            >
              No matches yet.
            </Text>
            <Text
              className="text-ink-mid"
              style={{
                fontSize: 14,
                lineHeight: 21,
                marginTop: 8,
                textAlign: 'center',
              }}
            >
              Keep swiping in Discover.
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <View className="flex-1">
            <MatchCard match={item} onPress={() => setSelectedMatch(item)} />
          </View>
        )}
      />
      <MatchSheet
        match={selectedMatch}
        visible={selectedMatch != null}
        onClose={() => setSelectedMatch(null)}
      />
    </SafeAreaView>
  );
}

// ── MatchesScreen ─────────────────────────────────────────────────────────────

export default function MatchesScreen() {
  return (
    <ScreenSuspense>
      <MatchesList />
    </ScreenSuspense>
  );
}
