import { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { colors } from '@/constants/theme';
import { useWingSwipe } from '@/hooks/use-wing-swipe';
import { View, Text, Pressable, ScrollView, TextInput, SafeAreaView } from '@/lib/tw';
import { NavHeader } from '@/components/ui/NavHeader';
import { PhotoRect } from '@/components/ui/PhotoRect';
import { Pill } from '@/components/ui/Pill';
import { Sprout } from '@/components/ui/Sprout';
import { useGetApiProfilesUserIdSuspense } from '@/lib/api/generated/profiles/profiles';
import type { WingProfile } from '@/lib/api/generated/model';
import { useGetApiWingPoolSuspense } from '@/lib/api/generated/wing-pool/wing-pool';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { cardButtonShadow } from '@/lib/styles';

const PAGE_SIZE = 20;

// ── WingCardView ──────────────────────────────────────────────────────────────

function WingCardView({ card }: { card: WingProfile }) {
  return (
    <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
      <PhotoRect uri={card.firstPhoto} ratio={4 / 5} />
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
  const insets = useSafeAreaInsets();
  const [note, setNote] = useState('');

  function handleSend(withNote: boolean) {
    onSend(withNote && note.trim().length > 0 ? note.trim() : null);
    setNote('');
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onDismiss}>
      <View className="flex-1 bg-black/45">
        <Pressable className="flex-1" onPress={onDismiss} />
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ position: 'absolute', bottom: 0, left: 0, right: 0 }}
        >
          <View
            className="bg-white rounded-tl-[20px] rounded-tr-[20px] px-6 pt-3"
            style={{ paddingBottom: insets.bottom + 20 }}
          >
            <View className="self-center w-9 h-1 rounded-[2px] bg-fg-ghost mb-5" />
            <Text className="text-lg font-bold text-fg mb-1.5">Add a note?</Text>
            <Text className="text-sm text-fg-muted leading-5 mb-4">
              Let them know why you think they{"'"}d get along. (Optional)
            </Text>
            <TextInput
              className="border-[1.5px] border-separator rounded-xl px-4 py-[14px] text-sm text-fg bg-white min-h-[100px]"
              placeholder="She loves hiking and has a great laugh..."
              placeholderTextColor={colors.inkGhost}
              multiline
              numberOfLines={4}
              value={note}
              onChangeText={setNote}
              textAlignVertical="top"
            />
            <View className="mt-4 gap-[10px]">
              <Sprout block variant="secondary" onPress={() => handleSend(false)}>
                Skip & Send
              </Sprout>
              <Sprout block onPress={() => handleSend(true)}>
                Add Note & Send
              </Sprout>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
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
  const { data: initialPool } = useGetApiWingPoolSuspense({
    daterId,
    pageSize: PAGE_SIZE,
    pageOffset: 0,
  });

  const { pool, index, suggest, decline } = useWingSwipe(daterId, initialPool);
  const card = pool[index] ?? null;

  const daterName = daterContext?.chosenName ?? '';
  const firstName = daterName.split(' ')[0] || daterName;

  const [noteVisible, setNoteVisible] = useState(false);

  async function handleSuggest(note: string | null) {
    setNoteVisible(false);
    await suggest(note);
  }

  return (
    <>
      <NavHeader
        back
        title={daterName ? `Swiping for ${firstName}` : 'Wing Mode'}
        onBack={() => router.back()}
      />

      <View className="flex-1">
        {card != null ? (
          <WingCardView card={card} />
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
