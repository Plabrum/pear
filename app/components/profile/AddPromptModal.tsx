import { useState } from 'react';
import { FlatList, KeyboardAvoidingView, Modal, Platform, StyleSheet } from 'react-native';
import { z } from 'zod';

import { colors } from '@/constants/theme';
import { getApiPromptTemplates, postApiProfilePrompts } from '@/lib/api/generated/prompts/prompts';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { cn } from '@/lib/cn';
import { View, Text, ScrollView, Pressable, SafeAreaView } from '@/lib/tw';
import { createForm, RootError, useFormSubmit } from '@/lib/forms';

const answerSchema = z.object({ answer: z.string().trim().min(1) });
const answerForm = createForm(answerSchema);

interface Props {
  visible: boolean;
  onClose: () => void;
  usedTemplateIds: Set<string>;
  onAdded: () => void;
}

function HeaderSave() {
  const { submit, isValid, isSubmitting } = useFormSubmit();
  const disabled = !isValid || isSubmitting;
  return (
    <Pressable
      onPress={submit}
      disabled={disabled}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
    >
      <Text className={cn('text-sm font-semibold text-accent', disabled && 'opacity-40')}>
        {isSubmitting ? 'Saving…' : 'Save'}
      </Text>
    </Pressable>
  );
}

function HeaderRow({
  title,
  onClose,
  right,
}: {
  title: string;
  onClose: () => void;
  right?: React.ReactNode;
}) {
  return (
    <View
      className="flex-row items-center justify-between px-5 py-[14px] bg-white"
      style={{ borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider }}
    >
      <Pressable onPress={onClose} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
        <Text className="text-sm text-fg-muted">Cancel</Text>
      </Pressable>
      <Text className="text-base font-semibold text-fg">{title}</Text>
      <View>{right ?? <View style={{ width: 36 }} />}</View>
    </View>
  );
}

export function AddPromptModal({ visible, onClose, usedTemplateIds, onAdded }: Props) {
  const [templates, setTemplates] = useState<{ id: string; question: string }[]>([]);
  const [selected, setSelected] = useState<{ id: string; question: string } | null>(null);

  const onOpen = async () => {
    setSelected(null);
    const list = await getApiPromptTemplates();
    setTemplates(list.filter((t) => !usedTemplateIds.has(t.id)));
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
      onShow={onOpen}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}
      >
        <View className="flex-1 bg-page">
          <SafeAreaView className="flex-1" edges={['top', 'bottom']}>
            {!selected ? (
              <>
                <HeaderRow title="Pick a Prompt" onClose={onClose} />
                <FlatList
                  data={templates}
                  keyExtractor={(t) => t.id}
                  renderItem={({ item }) => (
                    <Pressable
                      className="flex-row items-center bg-white px-5 py-4"
                      onPress={() => setSelected(item)}
                    >
                      <Text className="flex-1 text-sm text-fg pr-3">{item.question}</Text>
                      <IconSymbol name="chevron.right" size={15} color={colors.inkGhost} />
                    </Pressable>
                  )}
                  ItemSeparatorComponent={() => (
                    <View
                      style={{
                        height: StyleSheet.hairlineWidth,
                        backgroundColor: colors.divider,
                        marginLeft: 20,
                      }}
                    />
                  )}
                  ListEmptyComponent={
                    <Text className="p-9 text-center text-fg-muted text-sm">
                      You{"'"}ve answered all available prompts.
                    </Text>
                  }
                />
              </>
            ) : (
              <answerForm.Form
                defaultValues={{ answer: '' }}
                onSubmit={async ({ answer }) => {
                  await postApiProfilePrompts({
                    promptTemplateId: selected.id,
                    answer: answer.trim(),
                  });
                  onAdded();
                  onClose();
                }}
              >
                <HeaderRow title="Write Your Answer" onClose={onClose} right={<HeaderSave />} />
                <ScrollView contentContainerClassName="p-5">
                  <Pressable
                    onPress={() => setSelected(null)}
                    className="flex-row items-center gap-1 mb-4"
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  >
                    <IconSymbol name="chevron.left" size={13} color={colors.primary} />
                    <Text className="text-sm text-accent">Back to prompts</Text>
                  </Pressable>
                  <Text className="text-xl font-bold text-fg font-serif mb-5 leading-7">
                    {selected.question}
                  </Text>
                  <answerForm.TextField
                    name="answer"
                    placeholder="Write your answer…"
                    multiline
                    autoFocus
                    maxLength={300}
                    showCount
                    minHeightClass="min-h-[130px]"
                  />
                  <RootError />
                </ScrollView>
              </answerForm.Form>
            )}
          </SafeAreaView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
