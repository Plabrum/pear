// Registered form for `prompt_response_actions__create` — a winger/match comment
// on a dater's prompt. Conforms to the action-registry render contract; `objectData`
// is the prompt being responded to. Mirrors the look of the former inline
// ResponseModal so the UI is unchanged — only the wiring moves to the registry.
import { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/constants/theme';
import { View, Text, Pressable, TextInput } from '@/lib/tw';
import { Sprout } from '@/components/ui/Sprout';

type PromptContext = { id: string; question?: string | null };

export function PromptResponseForm({
  objectData,
  onSubmit,
  onClose,
  isSubmitting,
  isOpen,
}: {
  objectData?: unknown;
  onSubmit: (data: { profilePromptId: string; message: string }) => void;
  onClose: () => void;
  isSubmitting: boolean;
  isOpen: boolean;
}) {
  const prompt = objectData as PromptContext | undefined;
  const insets = useSafeAreaInsets();
  const [message, setMessage] = useState('');

  if (!prompt) return null;

  const handleSubmit = () => {
    if (!message.trim() || isSubmitting) return;
    onSubmit({ profilePromptId: prompt.id, message: message.trim() });
    setMessage('');
  };

  return (
    <Modal visible={isOpen} animationType="slide" transparent onRequestClose={onClose}>
      <View className="flex-1 bg-black/45">
        <Pressable className="flex-1" onPress={onClose} />
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
              {prompt.question ?? ''}
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
              <Sprout block onPress={handleSubmit} disabled={!message.trim()} loading={isSubmitting}>
                Send Comment
              </Sprout>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}
