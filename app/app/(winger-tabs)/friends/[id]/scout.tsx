import { useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { useSwipeDeck } from '@/hooks/use-swipe-deck';
import { View, Text, Pressable, ScrollView, SafeAreaView } from '@/lib/tw';
import { NavHeader } from '@/components/ui/NavHeader';
import { PhotoRect } from '@/components/ui/PhotoRect';
import { Pill } from '@/components/ui/Pill';
import { Sprout } from '@/components/ui/Sprout';
import { Sheet } from '@/components/ui/Sheet';
import { ForwardSheet } from '@/components/ui/ForwardSheet';
import { KitField, TextareaControl } from '@/lib/forms/fields';
import { useGetApiProfilesUserIdSuspense } from '@/lib/api/generated/profiles/profiles';
import { useGetApiWingpeopleSuspense } from '@/lib/api/generated/contacts/contacts';
import type { SwipeProfile } from '@/lib/api/generated/model';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { cardButtonShadow } from '@/lib/styles';
import { colors } from '@/constants/theme';

// ── WingCardView ──────────────────────────────────────────────────────────────

function WingCardView({ card, daterId }: { card: SwipeProfile; daterId: string }) {
  const { data: wingpeopleData } = useGetApiWingpeopleSuspense();
  const [forwardOpen, setForwardOpen] = useState(false);

  return (
    <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
      <View>
        <PhotoRect uri={card.firstPhoto} ratio={4 / 5} />
        {wingpeopleData.wingingFor.length > 0 && (
          <Pressable
            onPress={() => setForwardOpen(true)}
            className="absolute top-3 right-3 w-9 h-9 rounded-full justify-center items-center bg-black/40"
          >
            <Ionicons name="arrow-redo-outline" size={16} color={colors.white} />
          </Pressable>
        )}
      </View>
      <View className="p-4">
        <Text className="text-3xl font-serif text-fg font-bold">
          {card.chosenName}, {card.age}
        </Text>
        <Text className="text-sm text-fg-muted mt-1 mb-3">{card.city}</Text>
        {card.interests.length > 0 && (
          <View className="flex-row flex-wrap gap-2 mb-4">
            {card.interests.map((interest) => (
              <Pill key={interest} label={interest} />
            ))}
          </View>
        )}
        {card.bio != null && (
          <Text className="text-sm text-fg-muted leading-[22px]">{card.bio}</Text>
        )}
      </View>
      <ForwardSheet
        visible={forwardOpen}
        recipientId={card.userId}
        recipientProfileId={card.profileId}
        recipientName={card.chosenName}
        recipientGender={card.gender}
        wingingFor={wingpeopleData.wingingFor}
        excludeDaterId={daterId}
        onClose={() => setForwardOpen(false)}
      />
    </ScrollView>
  );
}

// ── NoteModal ─────────────────────────────────────────────────────────────────

function NoteModal({
  visible,
  onSend,
  onDismiss,
}: {
  visible: boolean;
  onSend: (note: string | null) => void;
  onDismiss: () => void;
}) {
  const [note, setNote] = useState('');

  function handleSend(withNote: boolean) {
    onSend(withNote && note.trim().length > 0 ? note.trim() : null);
    setNote('');
  }

  return (
    <Sheet
      visible={visible}
      onClose={onDismiss}
      onShow={() => setNote('')}
      title="Add a note?"
      subtitle="Let them know why you think they'd get along."
      footer={
        <View style={{ gap: 10 }}>
          <Sprout block size="lg" onPress={() => handleSend(true)} disabled={!note.trim()}>
            Add note & send
          </Sprout>
          <Sprout block variant="secondary" onPress={() => handleSend(false)}>
            Skip & send
          </Sprout>
        </View>
      }
    >
      <KitField label="Note" optional>
        <TextareaControl
          value={note}
          onChange={setNote}
          placeholder="She loves hiking and has a great laugh…"
          autoFocus
        />
      </KitField>
    </Sheet>
  );
}

// ── EmptyState ────────────────────────────────────────────────────────────────

function EmptyState({ daterName }: { daterName: string }) {
  return (
    <View className="flex-1 justify-center items-center p-6">
      <Text className="text-base text-fg-muted text-center leading-6">
        You{"'"}ve gone through everyone in {daterName}
        {"'"}s area. Check back soon.
      </Text>
    </View>
  );
}

// ── WingSwipeContent ──────────────────────────────────────────────────────────

function WingSwipeContent() {
  const router = useRouter();
  const { id: daterId } = useLocalSearchParams<{ id: string }>();

  const { data: daterContext } = useGetApiProfilesUserIdSuspense(daterId);

  // daterId scopes the feed and is injected into every action body (formContext).
  const deck = useSwipeDeck({
    params: { daterId },
    actionGroup: 'dating_profile_swipe_actions',
    formContext: { daterId },
  });
  const card = deck.currentCard;

  const daterName = daterContext?.chosenName ?? '';
  const firstName = daterName.split(' ')[0] || daterName;

  const [noteVisible, setNoteVisible] = useState(false);

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
      <NavHeader
        back
        title={daterName ? `Swiping for ${firstName}` : 'Wing Mode'}
        onBack={() => router.back()}
      />

      <View className="flex-1">
        {card != null ? (
          <WingCardView card={card} daterId={daterId} />
        ) : (
          <EmptyState daterName={firstName || 'them'} />
        )}
      </View>

      {card != null && (
        <View className="flex-row justify-center items-center gap-[40px] py-5 pb-7">
          <Pressable
            className="w-16 h-16 rounded-[32px] justify-center items-center bg-white"
            style={cardButtonShadow}
            onPress={decline}
          >
            <Text className="text-2xl text-fg-muted">✕</Text>
          </Pressable>
          <Pressable
            className="w-16 h-16 rounded-[32px] justify-center items-center bg-accent"
            style={cardButtonShadow}
            onPress={() => setNoteVisible(true)}
          >
            <Text className="text-2xl text-white">♥</Text>
          </Pressable>
        </View>
      )}

      <NoteModal
        visible={noteVisible}
        onSend={handleSuggest}
        onDismiss={() => setNoteVisible(false)}
      />
    </>
  );
}

// ── WingSwipeScreen ───────────────────────────────────────────────────────────

export default function WingSwipeScreen() {
  return (
    <SafeAreaView className="flex-1 bg-page" edges={['top']}>
      <ScreenSuspense>
        <WingSwipeContent />
      </ScreenSuspense>
    </SafeAreaView>
  );
}
