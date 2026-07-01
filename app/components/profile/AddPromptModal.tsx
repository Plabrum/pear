import { useState } from 'react';
import { FlatList, StyleSheet } from 'react-native';

import { colors } from '@/constants/theme';
import { getApiPromptTemplates } from '@/lib/api/generated/prompts/prompts';
import { addProfilePrompt } from '@/lib/api/actions';
import type { CreateProfilePromptData } from '@/lib/api/generated/model';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { View, Text, Pressable } from '@/lib/tw';
import { FullSheet } from '@/components/ui/FullSheet';
import { createTypedForm } from '@/lib/forms/typed-form';

const AnswerForm = createTypedForm<CreateProfilePromptData>();

interface Props {
  visible: boolean;
  onClose: () => void;
  usedTemplateIds: Set<string>;
  onAdded: () => void;
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
    <>
      {/* Step 1 — pick a template (owns its own FlatList scroll). */}
      <FullSheet
        visible={visible && !selected}
        onClose={onClose}
        onShow={onOpen}
        step="Step 1 of 2"
        title="Pick a prompt"
        scrollable={false}
      >
        <FlatList
          data={templates}
          keyExtractor={(t) => t.id}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => setSelected(item)}
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                paddingVertical: 16,
              }}
            >
              <Text style={{ flex: 1, fontSize: 15, color: colors.ink, paddingRight: 12 }}>
                {item.question}
              </Text>
              <IconSymbol name="chevron.right" size={15} color={colors.inkDim} />
            </Pressable>
          )}
          ItemSeparatorComponent={() => (
            <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: colors.divider }} />
          )}
          ListEmptyComponent={
            <Text style={{ padding: 36, textAlign: 'center', color: colors.inkMid, fontSize: 14 }}>
              You&apos;ve answered all available prompts.
            </Text>
          }
        />
      </FullSheet>

      {/* Step 2 — write the answer. */}
      <AnswerForm.FormFullSheet
        visible={visible && !!selected}
        onClose={onClose}
        onBack={() => setSelected(null)}
        step="Step 2 of 2"
        title={selected?.question}
        submitLabel="Save"
        defaultValues={{ answer: '' }}
        onSubmit={async ({ answer }) => {
          if (!selected) return;
          await addProfilePrompt({ promptTemplateId: selected.id, answer: answer.trim() });
          onAdded();
          onClose();
        }}
      >
        <AnswerForm.TextareaField
          name="answer"
          label="Your answer"
          placeholder="Write your answer…"
          maxLength={300}
          autoFocus
        />
      </AnswerForm.FormFullSheet>
    </>
  );
}
