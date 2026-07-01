import { useState } from 'react';
import { Image, Platform, StyleSheet } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { useSwipeDeck } from '@/hooks/use-swipe-deck';
import { View, Text, Pressable, ScrollView, SafeAreaView } from '@/lib/tw';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { Pill } from '@/components/ui/Pill';
import { ForwardSheet } from '@/components/ui/ForwardSheet';
import { NoteModal } from '@/components/ui/NoteModal';
import { useGetApiProfilesUserIdSuspense } from '@/lib/api/generated/profiles/profiles';
import type { SwipeProfile } from '@/lib/api/generated/model';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { cardButtonShadow } from '@/lib/styles';
import { colors } from '@/constants/theme';

// ── WingCardEditorial ────────────────────────────────────────────────────────

function WingCardEditorial({
  card,
  daterFirstName,
}: {
  card: SwipeProfile;
  daterFirstName: string;
}) {
  return (
    <View
      className="bg-canvas"
      style={{
        width: '100%',
        height: '100%',
        borderRadius: 22,
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: colors.divider,
        ...Platform.select({
          ios: {
            shadowColor: '#000',
            shadowOffset: { width: 0, height: 12 },
            shadowOpacity: 0.1,
            shadowRadius: 24,
          },
          android: { elevation: 6 },
        }),
      }}
    >
      <View
        style={{
          paddingTop: 20,
          paddingHorizontal: 18,
          paddingBottom: 8,
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'baseline',
        }}
      >
        <Text
          className="text-ink-dim"
          style={{
            fontSize: 10,
            letterSpacing: 2,
            textTransform: 'uppercase',
            fontWeight: '600',
          }}
        >
          {daterFirstName ? `For ${daterFirstName}` : 'Wing pick'}
        </Text>
        <Text
          className="text-primary"
          style={{
            fontSize: 10,
            letterSpacing: 1.5,
            textTransform: 'uppercase',
            fontWeight: '600',
          }}
        >
          Suggestion
        </Text>
      </View>

      <View style={{ paddingHorizontal: 18 }}>
        <Text
          className="font-serif text-ink"
          style={{
            fontSize: 44,
            lineHeight: 44,
            letterSpacing: -1,
          }}
        >
          {card.chosenName},
        </Text>
        <Text
          className="font-serif text-primary"
          style={{
            fontSize: 44,
            lineHeight: 44,
            letterSpacing: -1,
            fontStyle: 'italic',
          }}
        >
          {card.age}
        </Text>
        {card.city != null && (
          <Text className="text-ink-mid" style={{ fontSize: 13, marginTop: 6 }}>
            {card.city}
          </Text>
        )}
      </View>

      <ScrollView
        contentContainerStyle={{ padding: 18, paddingTop: 14, paddingBottom: 20, gap: 12 }}
        showsVerticalScrollIndicator={false}
      >
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View
            style={{
              flex: 1,
              aspectRatio: 3 / 4,
              borderRadius: 12,
              overflow: 'hidden',
              backgroundColor: colors.muted,
            }}
          >
            {card.firstPhoto != null && (
              <Image
                source={{ uri: card.firstPhoto }}
                style={StyleSheet.absoluteFill}
                resizeMode="cover"
              />
            )}
          </View>
          <View style={{ flex: 1, gap: 8 }}>
            {card.bio != null && (
              <Text className="text-ink-mid" style={{ fontSize: 12.5, lineHeight: 18 }}>
                {card.bio}
              </Text>
            )}
            {card.interests.length > 0 && (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                {card.interests.slice(0, 3).map((interest) => (
                  <Pill key={interest} label={interest} tone="outline" size="sm" />
                ))}
              </View>
            )}
          </View>
        </View>

        {card.interests.length > 3 && (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {card.interests.slice(3).map((interest) => (
              <Pill key={interest} label={interest} tone="cream" size="sm" />
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

// ── EmptyState ───────────────────────────────────────────────────────────────

function EmptyState({ daterFirstName }: { daterFirstName: string }) {
  return (
    <View className="flex-1 items-center justify-center" style={{ padding: 24 }}>
      <Text
        className="font-serif text-ink"
        style={{ fontSize: 24, letterSpacing: -0.3, textAlign: 'center' }}
      >
        {`That's everyone for now.`}
      </Text>
      <Text
        className="text-ink-dim"
        style={{ fontSize: 13, marginTop: 8, textAlign: 'center', lineHeight: 20 }}
      >
        {`You've gone through ${daterFirstName || 'their'}'s pool. Check back soon for new picks.`}
      </Text>
    </View>
  );
}

// ── WingSwipeContent ─────────────────────────────────────────────────────────

function WingSwipeContent() {
  const router = useRouter();
  const { daterId } = useLocalSearchParams<{ daterId: string }>();

  const { data: daterContext } = useGetApiProfilesUserIdSuspense(daterId);

  // daterId scopes the feed and is injected into every action body (formContext).
  const deck = useSwipeDeck({
    params: { daterId },
    actionGroup: 'dating_profile_swipe_actions',
    formContext: { daterId },
  });
  const card = deck.currentCard;
  const remaining = deck.remaining;
  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();

  const daterName = daterContext?.chosenName ?? '';
  const firstName = daterName.split(' ')[0] || daterName;

  const forwardTargets = wingpeopleData.wingingFor.filter((r) => r.dater?.id !== daterId);

  const [noteVisible, setNoteVisible] = useState(false);
  const [forwardOpen, setForwardOpen] = useState(false);

  // Suggest targets the DatingProfile (profileId); daterId comes from formContext.
  async function handleSuggest(note: string | null) {
    setNoteVisible(false);
    if (card) await deck.run(card, 'suggest', { note });
  }

  // Fire-and-forget — no rollback (matches prior behavior).
  const decline = () => {
    if (card) void deck.run(card, 'decline', undefined, { rollback: false });
  };

  return (
    <>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 10,
          paddingHorizontal: 12,
          paddingTop: 8,
          paddingBottom: 12,
          borderBottomWidth: 1,
          borderBottomColor: colors.divider,
        }}
      >
        <Pressable
          onPress={() => router.back()}
          hitSlop={12}
          style={{ padding: 8, marginLeft: -4 }}
        >
          <Ionicons name="chevron-back" size={22} color={colors.ink} />
        </Pressable>
        <FaceAvatar name={daterName || '?'} size={32} photoUri={daterContext?.avatarUrl ?? null} />
        <View style={{ flex: 1 }}>
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '600' }}>
            Swiping for {firstName || 'them'}
          </Text>
          <Text className="text-ink-dim" style={{ fontSize: 11.5, marginTop: 1 }}>
            Suggestions go to {firstName || 'them'} for review
          </Text>
        </View>
        {remaining > 0 && (
          <Pill tone="leaf" size="sm">
            {remaining} left
          </Pill>
        )}
      </View>

      <View style={{ flex: 1, padding: 14 }}>
        {card != null ? (
          <>
            <WingCardEditorial card={card} daterFirstName={firstName} />
            {forwardTargets.length > 0 && (
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
                  backgroundColor: 'rgba(31,27,22,0.15)',
                  borderWidth: 1,
                  borderColor: 'rgba(31,27,22,0.12)',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Ionicons name="arrow-redo-outline" size={16} color={colors.inkMid} />
              </Pressable>
            )}
          </>
        ) : (
          <EmptyState daterFirstName={firstName} />
        )}
      </View>

      {card != null && forwardTargets.length > 0 && (
        <ForwardSheet
          visible={forwardOpen}
          recipientId={card.userId}
          recipientProfileId={card.profileId}
          recipientName={card.chosenName}
          wingingFor={wingpeopleData.wingingFor}
          excludeDaterId={daterId}
          onClose={() => setForwardOpen(false)}
        />
      )}

      {card != null && (
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 24,
            paddingBottom: 28,
            paddingTop: 6,
          }}
        >
          <Pressable
            onPress={decline}
            className="bg-surface"
            style={[
              {
                width: 60,
                height: 60,
                borderRadius: 30,
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
            onPress={() => setNoteVisible(true)}
            className="bg-primary"
            style={[
              {
                width: 60,
                height: 60,
                borderRadius: 30,
                alignItems: 'center',
                justifyContent: 'center',
              },
              cardButtonShadow,
            ]}
          >
            <Ionicons name="heart" size={24} color={colors.white} />
          </Pressable>
        </View>
      )}

      <NoteModal
        visible={noteVisible}
        daterFirstName={firstName}
        subjectName={card?.chosenName ?? 'they'}
        onSend={handleSuggest}
        onDismiss={() => setNoteVisible(false)}
      />
    </>
  );
}

// ── WingSwipeScreen ──────────────────────────────────────────────────────────

export default function WingSwipeScreen() {
  return (
    <SafeAreaView className="flex-1 bg-canvas" edges={['top']}>
      <ScreenSuspense>
        <WingSwipeContent />
      </ScreenSuspense>
    </SafeAreaView>
  );
}
