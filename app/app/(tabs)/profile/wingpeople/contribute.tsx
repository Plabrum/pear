import { useState } from 'react';
import { Platform, StyleSheet } from 'react-native';
import PulseSpinner from '@/components/ui/PulseSpinner';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import { toast } from 'sonner-native';
import type { RootStackParamList } from '@/navigation/types';
import { useQueryClient } from '@tanstack/react-query';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { useAuth } from '@/context/auth';
import {
  useGetApiProfilesUserIdSuspense,
  getGetApiProfilesUserIdQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { pickAndResizePhoto } from '@/lib/photos';
import { addPromptResponse } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import { useUploadProfilePhoto } from '@/hooks/use-upload-profile-photo';

import { View, Text, Pressable, ScrollView, SafeAreaView } from '@/lib/tw';
import { PhotoRect } from '@/components/ui/PhotoRect';
import { Sprout } from '@/components/ui/Sprout';
import { Sheet } from '@/components/ui/Sheet';
import { KitField, TextareaControl } from '@/lib/forms/fields';
import { SectionLabel } from '@/components/ui/SectionLabel';
import { colors } from '@/constants/theme';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

// Preserve this screen's flush-left section heading spacing.
const sectionLabelStyle = {
  letterSpacing: 1.2,
  paddingHorizontal: 0,
  paddingTop: 18,
  paddingBottom: 10,
};

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
  const [message, setMessage] = useState('');

  const handleSubmit = () => {
    if (!message.trim()) return;
    onSubmit(message.trim());
    setMessage('');
  };

  return (
    <Sheet
      visible={visible}
      onClose={onDismiss}
      onShow={() => setMessage('')}
      title="Add a comment"
      subtitle={promptQuestion}
      footer={
        <Sprout block size="lg" onPress={handleSubmit} disabled={!message.trim()}>
          Send comment
        </Sprout>
      }
    >
      <KitField label="Comment">
        <TextareaControl
          value={message}
          onChange={setMessage}
          placeholder={`Why ${daterFirstName || 'they'} should answer this…`}
          autoFocus
        />
      </KitField>
    </Sheet>
  );
}

// ── ContributeContent ────────────────────────────────────────────────────────

function ContributeContent() {
  const navigation = useNavigation();
  const { userId: wingerId } = useAuth();
  const { params } = useRoute<RouteProp<RootStackParamList, 'WingpeopleContribute'>>();
  const { daterId } = params;
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
  const approvedPhotos = photos.filter((p) => p.status === 'approved');
  const myPendingPhotos = photos.filter(
    (p) => p.status === 'pending' && p.suggesterId === wingerId
  );

  const handleSuggestPhoto = async () => {
    const uri = await pickAndResizePhoto({ aspect: [3, 4] });
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
    const result = await addPromptResponse({ profilePromptId: promptId, message }).catch((err) => {
      toastError(err, "Couldn't send comment. Try again.");
      return null;
    });
    if (result == null) return;
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
          borderBottomColor: colors.divider,
        }}
      >
        <Pressable
          onPress={() => navigation.goBack()}
          hitSlop={12}
          style={{ padding: 8, marginLeft: -4 }}
        >
          <Ionicons name="chevron-back" size={22} color={colors.ink} />
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
        <SectionLabel style={sectionLabelStyle}>Photos</SectionLabel>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {approvedPhotos.map((photo) => (
            <View key={photo.id} style={{ width: '31.5%' }}>
              <PhotoRect uri={photo.storageUrl} ratio={3 / 4} />
            </View>
          ))}
          {myPendingPhotos.map((photo) => (
            <View key={photo.id} style={{ width: '31.5%', position: 'relative' }}>
              <PhotoRect uri={photo.storageUrl} ratio={3 / 4} blur />
              <View
                style={{
                  ...StyleSheet.absoluteFill,
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
              borderColor: colors.leaf,
              borderStyle: 'dashed',
              backgroundColor: colors.leafSoft,
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
              padding: 8,
              opacity: uploading ? 0.5 : 1,
            }}
          >
            {uploading ? (
              <PulseSpinner color={colors.leaf} />
            ) : (
              <>
                <Ionicons name="camera-outline" size={20} color={colors.leaf} />
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

        <SectionLabel style={sectionLabelStyle}>Prompts</SectionLabel>
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
                    borderColor: colors.divider,
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
                      <Ionicons name="checkmark" size={14} color={colors.leaf} />
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
