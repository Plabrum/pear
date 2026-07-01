import { useState } from 'react';
import { Dimensions, KeyboardAvoidingView, Modal, Platform, StyleSheet } from 'react-native';
import PulseSpinner from '@/components/ui/PulseSpinner';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { toast } from 'sonner-native';
import { useQueryClient } from '@tanstack/react-query';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/constants/theme';
import { useAuth } from '@/context/auth';
import {
  useGetApiProfilesUserIdSuspense,
  getGetApiProfilesUserIdQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { getPhotoUrl, pickAndResizePhoto } from '@/lib/photos';
import { postApiPromptResponses } from '@/lib/api/generated/prompts/prompts';
import { useUploadProfilePhoto } from '@/hooks/use-upload-profile-photo';

import { View, Text, Pressable, ScrollView, SafeAreaView, TextInput } from '@/lib/tw';
import { NavHeader } from '@/components/ui/NavHeader';
import { PhotoRect } from '@/components/ui/PhotoRect';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { Sprout } from '@/components/ui/Sprout';
import { IconSymbol } from '@/components/ui/icon-symbol';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

const PHOTO_COL = (Dimensions.get('window').width - 20 * 2 - 8) / 2;

function ResponseModal({
  visible,
  promptQuestion,
  onSubmit,
  onDismiss,
}: {
  visible: boolean;
  promptQuestion: string;
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
      <View className="flex-1 bg-black/45">
        <Pressable className="flex-1" onPress={onDismiss} />
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ position: 'absolute', bottom: 0, left: 0, right: 0 }}
        >
          <View
            className="bg-white rounded-t-[20px] px-6 pt-3"
            style={{ paddingBottom: insets.bottom + 20 }}
          >
            <View className="self-center w-9 h-1 rounded-full bg-fg-ghost mb-5" />
            <Text className="text-xs font-semibold text-fg-muted uppercase tracking-[0.6px] mb-1">
              Prompt
            </Text>
            <Text className="text-sm font-semibold text-fg mb-4" numberOfLines={2}>
              {promptQuestion}
            </Text>
            <TextInput
              className="border-[1.5px] border-separator rounded-xl px-4 py-[14px] text-sm text-fg bg-white min-h-[100px]"
              placeholder="Write a comment on this prompt..."
              placeholderTextColor={colors.inkGhost}
              multiline
              numberOfLines={4}
              value={message}
              onChangeText={setMessage}
              textAlignVertical="top"
              autoFocus
            />
            <View className="mt-4">
              <Sprout block onPress={handleSubmit} disabled={!message.trim()}>
                Send Comment
              </Sprout>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

function FriendDetailContent() {
  const router = useRouter();
  const { userId: wingerId } = useAuth();
  const { id: daterId } = useLocalSearchParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data } = useGetApiProfilesUserIdSuspense(daterId);
  const { upload, isPending: uploading } = useUploadProfilePhoto();
  const [respondingToPrompt, setRespondingToPrompt] = useState<{
    id: string;
    question: string;
  } | null>(null);

  const daterName = data?.chosenName ?? 'them';
  const firstName = daterName.split(' ')[0] || daterName;

  const approvedPhotos = (data?.datingProfile?.photos ?? []).filter((p) => p.approvedAt !== null);
  const myPendingPhotos = (data?.datingProfile?.photos ?? []).filter(
    (p) => p.approvedAt === null && p.suggesterId === wingerId
  );

  const handleSuggestPhoto = async () => {
    const uri = await pickAndResizePhoto();
    if (!uri) return;
    const filename = `${Date.now()}.jpg`;
    const nextOrder = approvedPhotos.length + myPendingPhotos.length;
    const ok = await upload(data!.datingProfile!.id, uri, filename, nextOrder);
    if (!ok) return;
    queryClient.invalidateQueries({ queryKey: getGetApiProfilesUserIdQueryKey(daterId) });
    toast.success(`Photo suggested — ${firstName} will review it.`);
  };

  const handleSubmitResponse = async (message: string) => {
    if (!respondingToPrompt) return;
    const promptId = respondingToPrompt.id;
    setRespondingToPrompt(null);
    try {
      await postApiPromptResponses({ profilePromptId: promptId, message });
      toast.success(`Comment sent — ${firstName} will review it.`);
    } catch {
      toast.error("Couldn't send comment. Try again.");
    }
  };

  return (
    <>
      <NavHeader back title={`Winging for ${firstName}`} onBack={() => router.back()} />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerClassName="pb-32">
        <View className="px-5 pt-2 pb-3 flex-row items-center" style={{ gap: 14 }}>
          <FaceAvatar name={daterName} size={64} photoUri={data?.avatarUrl ?? null} />
          <View style={{ flex: 1 }}>
            <Text className="font-serif text-ink" style={{ fontSize: 22, letterSpacing: -0.3 }}>
              {daterName}
            </Text>
            {data?.datingProfile?.city ? (
              <Text className="text-xs mt-0.5 text-ink-dim">{data.datingProfile.city}</Text>
            ) : null}
          </View>
        </View>

        <View className="px-5 pb-3 flex-row" style={{ gap: 10 }}>
          <View style={{ flex: 1 }}>
            <Sprout
              block
              size="md"
              onPress={() => router.push(`/(winger-tabs)/scout/${daterId}` as any)}
            >
              Scout for {firstName}
            </Sprout>
          </View>
          <View style={{ flex: 1 }}>
            <Sprout
              block
              size="md"
              variant="secondary"
              onPress={handleSuggestPhoto}
              loading={uploading}
            >
              Suggest photo
            </Sprout>
          </View>
        </View>

        <Text className="text-xs font-bold text-fg-subtle uppercase tracking-[0.6px] px-5 pt-4 pb-[10px]">
          Photos
        </Text>

        {approvedPhotos.length === 0 && myPendingPhotos.length === 0 ? (
          <Text className="text-sm text-fg-muted px-5 mb-4">No photos yet.</Text>
        ) : (
          <View className="flex-row flex-wrap gap-2 px-5 mb-4">
            {approvedPhotos.map((photo) => (
              <View key={photo.id} style={{ width: PHOTO_COL }}>
                <PhotoRect uri={getPhotoUrl(photo.storageUrl)} ratio={4 / 5} />
              </View>
            ))}
            {myPendingPhotos.map((photo) => (
              <View key={photo.id} style={{ width: PHOTO_COL, position: 'relative' }}>
                <PhotoRect uri={getPhotoUrl(photo.storageUrl)} ratio={4 / 5} blur />
                <View className="absolute bottom-2 left-0 right-0 items-center">
                  <View
                    className="rounded-full px-3 py-1"
                    style={{ backgroundColor: 'rgba(0,0,0,0.55)' }}
                  >
                    <Text className="text-white text-xs font-semibold">Pending approval</Text>
                  </View>
                </View>
              </View>
            ))}
          </View>
        )}

        <Pressable
          className="flex-row items-center justify-center gap-2 mx-5 border-[1.5px] border-accent border-dashed rounded-xl py-[14px] min-h-[52px]"
          onPress={handleSuggestPhoto}
          disabled={uploading}
        >
          {uploading ? (
            <PulseSpinner color={colors.primary} />
          ) : (
            <>
              <IconSymbol name="plus" size={18} color={colors.primary} />
              <Text className="text-sm font-semibold text-accent">Suggest a Photo</Text>
            </>
          )}
        </Pressable>

        <Text className="text-xs font-bold text-fg-subtle uppercase tracking-[0.6px] px-5 pt-6 pb-[10px]">
          Prompts
        </Text>

        {(data?.datingProfile?.prompts ?? []).length === 0 ? (
          <Text className="text-sm text-fg-muted px-5">
            {firstName} hasn{"'"}t added any prompts yet.
          </Text>
        ) : (
          <View className="px-5 gap-3">
            {(data?.datingProfile?.prompts ?? []).map((prompt) => {
              const question = prompt.template?.question ?? '';
              return (
                <View key={prompt.id} className="bg-white rounded-xl p-4">
                  <Text className="text-sm font-semibold text-accent mb-1.5">{question}</Text>
                  <Text className="text-base text-fg leading-[22px] font-serif">
                    {prompt.answer}
                  </Text>
                  <Pressable
                    className="mt-3 pt-3 flex-row items-center gap-1.5"
                    style={{
                      borderTopWidth: StyleSheet.hairlineWidth,
                      borderTopColor: colors.divider,
                    }}
                    onPress={() => setRespondingToPrompt({ id: prompt.id, question })}
                  >
                    <IconSymbol name="bubble.left" size={14} color={colors.primary} />
                    <Text className="text-sm font-semibold text-accent">Add Comment</Text>
                  </Pressable>
                </View>
              );
            })}
          </View>
        )}
      </ScrollView>

      <ResponseModal
        visible={respondingToPrompt !== null}
        promptQuestion={respondingToPrompt?.question ?? ''}
        onSubmit={handleSubmitResponse}
        onDismiss={() => setRespondingToPrompt(null)}
      />
    </>
  );
}

export default function FriendDetailScreen() {
  return (
    <SafeAreaView className="flex-1 bg-page" edges={['top']}>
      <ScreenSuspense>
        <FriendDetailContent />
      </ScreenSuspense>
    </SafeAreaView>
  );
}
