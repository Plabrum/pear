import { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform, StyleSheet } from 'react-native';
import PulseSpinner from '@/components/ui/PulseSpinner';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { toast } from 'sonner-native';
import { useQueryClient } from '@tanstack/react-query';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { useAuth } from '@/context/auth';
import {
  useGetApiProfilesUserIdSuspense,
  getGetApiProfilesUserIdQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { getPhotoUrl, pickAndResizePhoto } from '@/lib/photos';
import { postApiPromptResponses } from '@/lib/api/generated/prompts/prompts';
import { useUploadProfilePhoto } from '@/hooks/use-upload-profile-photo';

import { View, Text, Pressable, ScrollView, SafeAreaView, TextInput } from '@/lib/tw';
import { PhotoRect } from '@/components/ui/PhotoRect';
import { Sprout } from '@/components/ui/Sprout';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

const INK = '#1F1B16';
const INK3 = '#8B8170';
const LINE = 'rgba(31,27,22,0.10)';
const LEAF = '#5A8C3A';
const LEAF_SOFT = 'rgba(90,140,58,0.12)';

// ── SectionLabel ─────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: string }) {
  return (
    <Text
      className="text-ink-dim"
      style={{
        fontSize: 11,
        letterSpacing: 1.2,
        textTransform: 'uppercase',
        fontWeight: '600',
        paddingTop: 18,
        paddingBottom: 10,
      }}
    >
      {children}
    </Text>
  );
}

// ── ResponseModal ────────────────────────────────────────────────────────────

function ResponseModal({
  visible,
  promptQuestion,
  daterFirstName,
  onSubmit,
  onDismiss,
}: {
  visible: boolean;
  promptQuestion: string;
  daterFirstName: string;
  onSubmit: (message: string) => void;
  onDismiss: () => void;
}) {
  const insets = useSafeAreaInsets();
  const [message, setMessage] = useState('');

  const handleSubmit = () => {
    if (!message.trim()) return;
    onSubmit(message.trim());
    setMessage('');
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onDismiss}>
      <View className="flex-1" style={{ backgroundColor: 'rgba(31,27,22,0.45)' }}>
        <Pressable className="flex-1" onPress={onDismiss} />
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ position: 'absolute', bottom: 0, left: 0, right: 0 }}
        >
          <View
            className="bg-canvas"
            style={{
              borderTopLeftRadius: 24,
              borderTopRightRadius: 24,
              paddingHorizontal: 20,
              paddingTop: 14,
              paddingBottom: insets.bottom + 24,
            }}
          >
            <View
              style={{
                alignSelf: 'center',
                width: 40,
                height: 4,
                borderRadius: 2,
                backgroundColor: LINE,
                marginBottom: 14,
              }}
            />
            <Text
              className="text-ink-dim"
              style={{
                fontSize: 10,
                letterSpacing: 1.4,
                textTransform: 'uppercase',
                fontWeight: '600',
              }}
            >
              Prompt
            </Text>
            <Text
              className="font-serif text-ink"
              style={{
                fontSize: 19,
                lineHeight: 24,
                letterSpacing: -0.2,
                marginTop: 4,
                marginBottom: 12,
              }}
              numberOfLines={3}
            >
              {promptQuestion}
            </Text>
            <TextInput
              className="bg-surface text-ink"
              style={{
                width: '100%',
                minHeight: 100,
                borderWidth: 1,
                borderColor: LINE,
                borderRadius: 14,
                padding: 12,
                fontSize: 14,
                textAlignVertical: 'top',
              }}
              placeholder={`Why ${daterFirstName || 'they'} should answer this…`}
              placeholderTextColor={INK3}
              multiline
              value={message}
              onChangeText={setMessage}
              autoFocus
            />
            <View style={{ marginTop: 14 }}>
              <Sprout block onPress={handleSubmit} disabled={!message.trim()}>
                Send comment
              </Sprout>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

// ── ContributeContent ────────────────────────────────────────────────────────

function ContributeContent() {
  const router = useRouter();
  const { userId: wingerId } = useAuth();
  const { daterId } = useLocalSearchParams<{ daterId: string }>();
  const queryClient = useQueryClient();

  const { data } = useGetApiProfilesUserIdSuspense(daterId);
  const { upload, isPending: uploading } = useUploadProfilePhoto();

  const [respondingToPrompt, setRespondingToPrompt] = useState<{
    id: string;
    question: string;
  } | null>(null);
  const [respondedIds, setRespondedIds] = useState<Set<string>>(new Set());

  const daterName = data?.chosenName ?? 'them';
  const firstName = daterName.split(' ')[0] || daterName;

  const photos = data?.datingProfile?.photos ?? [];
  const approvedPhotos = photos.filter((p) => p.approvedAt !== null);
  const myPendingPhotos = photos.filter((p) => p.approvedAt === null && p.suggesterId === wingerId);

  const handleSuggestPhoto = async () => {
    const uri = await pickAndResizePhoto();
    if (!uri) return;
    if (data?.datingProfile == null) return;

    const filename = `${Date.now()}.jpg`;
    const nextOrder = approvedPhotos.length + myPendingPhotos.length;
    const ok = await upload(data.datingProfile.id, uri, filename, nextOrder);
    if (!ok) return;
    queryClient.invalidateQueries({ queryKey: getGetApiProfilesUserIdQueryKey(daterId) });
    toast.success(`Photo suggested — ${firstName} will review it.`);
  };

  const handleSubmitResponse = async (message: string) => {
    if (!respondingToPrompt) return;
    const promptId = respondingToPrompt.id;
    setRespondingToPrompt(null);
    const result = await postApiPromptResponses({ profilePromptId: promptId, message }).catch(
      () => null
    );
    if (result == null) {
      toast.error("Couldn't send comment. Try again.");
      return;
    }
    setRespondedIds((prev) => {
      const next = new Set(prev);
      next.add(promptId);
      return next;
    });
    toast.success(`Comment sent — ${firstName} will review it.`);
  };

  const prompts = data?.datingProfile?.prompts ?? [];

  return (
    <>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: 10,
          paddingHorizontal: 12,
          paddingTop: 8,
          paddingBottom: 10,
          borderBottomWidth: 1,
          borderBottomColor: LINE,
        }}
      >
        <Pressable
          onPress={() => router.back()}
          hitSlop={12}
          style={{ padding: 8, marginLeft: -4 }}
        >
          <Ionicons name="chevron-back" size={22} color={INK} />
        </Pressable>
        <Text
          className="font-serif text-ink"
          style={{ fontSize: 22, letterSpacing: -0.3, flex: 1 }}
        >
          {firstName}
          {"'"}s profile
        </Text>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
      >
        <SectionLabel>Photos</SectionLabel>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {approvedPhotos.map((photo) => (
            <View key={photo.id} style={{ width: '31.5%' }}>
              <PhotoRect uri={getPhotoUrl(photo.storageUrl)} ratio={3 / 4} />
            </View>
          ))}
          {myPendingPhotos.map((photo) => (
            <View key={photo.id} style={{ width: '31.5%', position: 'relative' }}>
              <PhotoRect uri={getPhotoUrl(photo.storageUrl)} ratio={3 / 4} blur />
              <View
                style={{
                  ...StyleSheet.absoluteFillObject,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Text
                  className="text-ink-mid"
                  style={{ fontSize: 10.5, fontWeight: '600', letterSpacing: 0.4 }}
                >
                  Pending
                </Text>
              </View>
            </View>
          ))}

          <Pressable
            onPress={handleSuggestPhoto}
            disabled={uploading}
            style={{
              width: '31.5%',
              aspectRatio: 3 / 4,
              borderRadius: 12,
              borderWidth: 1.5,
              borderColor: LEAF,
              borderStyle: 'dashed',
              backgroundColor: LEAF_SOFT,
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
              padding: 8,
              opacity: uploading ? 0.5 : 1,
            }}
          >
            {uploading ? (
              <PulseSpinner color={LEAF} />
            ) : (
              <>
                <Ionicons name="camera-outline" size={20} color={LEAF} />
                <Text
                  className="text-primary"
                  style={{
                    fontSize: 10.5,
                    fontWeight: '600',
                    textAlign: 'center',
                  }}
                >
                  Suggest photo
                </Text>
              </>
            )}
          </Pressable>
        </View>

        <SectionLabel>Prompts</SectionLabel>
        {prompts.length === 0 ? (
          <Text className="text-ink-dim" style={{ fontSize: 13, paddingVertical: 8 }}>
            {firstName} hasn{"'"}t added any prompts yet.
          </Text>
        ) : (
          <View style={{ gap: 10 }}>
            {prompts.map((prompt) => {
              const question = prompt.template?.question ?? '';
              const responded = respondedIds.has(prompt.id);
              return (
                <View
                  key={prompt.id}
                  className="bg-surface"
                  style={{
                    borderWidth: 1,
                    borderColor: LINE,
                    borderRadius: 16,
                    padding: 14,
                  }}
                >
                  <Text
                    className="text-ink-dim"
                    style={{
                      fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
                      fontSize: 10,
                      textTransform: 'uppercase',
                      letterSpacing: 1.4,
                    }}
                  >
                    {question}
                  </Text>
                  <Text
                    className="font-serif text-ink"
                    style={{
                      fontSize: 17,
                      lineHeight: 22,
                      marginTop: 4,
                      marginBottom: 8,
                      fontStyle: 'italic',
                    }}
                  >
                    “{prompt.answer}”
                  </Text>
                  {responded ? (
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <Ionicons name="checkmark" size={14} color={LEAF} />
                      <Text className="text-primary" style={{ fontSize: 12, fontWeight: '600' }}>
                        Comment sent — {firstName} will review
                      </Text>
                    </View>
                  ) : (
                    <Pressable
                      onPress={() => setRespondingToPrompt({ id: prompt.id, question })}
                      hitSlop={6}
                    >
                      <Text className="text-primary" style={{ fontSize: 12.5, fontWeight: '600' }}>
                        Add comment →
                      </Text>
                    </Pressable>
                  )}
                </View>
              );
            })}
          </View>
        )}
      </ScrollView>

      <ResponseModal
        visible={respondingToPrompt !== null}
        promptQuestion={respondingToPrompt?.question ?? ''}
        daterFirstName={firstName}
        onSubmit={handleSubmitResponse}
        onDismiss={() => setRespondingToPrompt(null)}
      />
    </>
  );
}

// ── Screen ───────────────────────────────────────────────────────────────────

export default function ContributeScreen() {
  return (
    <SafeAreaView className="flex-1 bg-canvas" edges={['top']}>
      <ScreenSuspense>
        <ContributeContent />
      </ScreenSuspense>
    </SafeAreaView>
  );
}
