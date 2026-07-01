import { useState } from 'react';
import { Pressable, ScrollView, Text, TextInput, View } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { Sprout } from '@/components/ui/Sprout';
import { Sheet } from '@/components/ui/Sheet';
import { colors } from '@/constants/theme';
import { useGetApiPromptTemplatesOnboardingSuspense } from '@/lib/api/generated/prompts/prompts';
import { addProfilePrompt } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import { StepHeader } from '@/components/onboarding/chrome';

type AddedPrompt = { id: string; question: string; answer: string };

export function PromptsStep({ onContinue }: { onContinue: () => void }) {
  const { data: templates } = useGetApiPromptTemplatesOnboardingSuspense();
  const [added, setAdded] = useState<AddedPrompt[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const remainingTemplates = templates.filter((t) => !added.some((a) => a.id === t.id));
  const activeTemplate = templates.find((t) => t.id === activeTemplateId) ?? null;

  function openPicker() {
    setActiveTemplateId(null);
    setDraft('');
    setPickerOpen(true);
  }

  function closePicker() {
    setPickerOpen(false);
    setActiveTemplateId(null);
    setDraft('');
  }

  async function saveAnswer() {
    const trimmed = draft.trim();
    if (!activeTemplate || !trimmed) return;
    setSubmitting(true);
    try {
      await addProfilePrompt({ promptTemplateId: activeTemplate.id, answer: trimmed });
      setAdded((prev) => [
        ...prev,
        { id: activeTemplate.id, question: activeTemplate.question, answer: trimmed },
      ]);
      closePicker();
    } catch (e) {
      toastError(e, 'Failed to save prompt');
    } finally {
      setSubmitting(false);
    }
  }

  const slots = Array.from({ length: 3 }, (_, i) => added[i] ?? null);
  const canContinue = added.length >= 1;

  return (
    <View className="flex-1">
      <ScrollView
        className="flex-1"
        contentContainerClassName="pb-4"
        keyboardShouldPersistTaps="handled"
      >
        <StepHeader
          kicker="Step 3 · Sound like you"
          title="Pick"
          accent="three prompts"
          sub="The good ones reveal something specific. Skip the bumper-sticker answers."
        />
        <View className="mt-5" style={{ gap: 10 }}>
          {slots.map((slot, i) => {
            const inner = (
              <>
                <View className="flex-row items-center justify-between">
                  <Text
                    className="font-mono text-foreground-subtle uppercase"
                    style={{ fontSize: 10, letterSpacing: 1.4 }}
                  >
                    {slot ? slot.question : `Prompt ${i + 1}`}
                  </Text>
                  {slot ? (
                    <Text className="text-primary" style={{ fontSize: 14 }}>
                      ✓
                    </Text>
                  ) : null}
                </View>
                <Text
                  className={cn(
                    'font-serif',
                    slot ? 'text-foreground' : 'text-foreground-subtle italic'
                  )}
                  style={{ fontSize: 16, lineHeight: 21 }}
                >
                  {slot ? `"${slot.answer}"` : 'Tap to answer'}
                </Text>
              </>
            );

            if (slot) {
              return (
                <View
                  key={i}
                  className="bg-surface rounded-2xl px-3.5 py-3 border border-primary/30"
                  style={{ gap: 4 }}
                >
                  {inner}
                </View>
              );
            }

            return (
              <Pressable
                key={i}
                onPress={openPicker}
                disabled={remainingTemplates.length === 0}
                className={cn(
                  'bg-surface rounded-2xl px-3.5 py-3 border border-border',
                  remainingTemplates.length === 0 && 'opacity-40'
                )}
                style={{ gap: 4 }}
              >
                {inner}
              </Pressable>
            );
          })}
        </View>
      </ScrollView>

      <Sheet
        visible={pickerOpen}
        onClose={closePicker}
        title={activeTemplate ? 'Your answer' : 'Pick a prompt'}
        subtitle={activeTemplate?.question}
        maxHeight={activeTemplate ? undefined : '70%'}
      >
        {activeTemplate ? (
          <View>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Your answer..."
              placeholderTextColor={colors.inkGhost}
              multiline
              autoFocus
              className="min-h-24 bg-surface rounded-xl border border-border px-3.5 py-3 text-base text-foreground"
              style={{ textAlignVertical: 'top' }}
            />
            <View className="flex-row mt-4" style={{ gap: 8 }}>
              <View className="flex-1">
                <Sprout
                  block
                  size="md"
                  variant="secondary"
                  onPress={() => {
                    setActiveTemplateId(null);
                    setDraft('');
                  }}
                >
                  Back
                </Sprout>
              </View>
              <View className="flex-1">
                <Sprout
                  block
                  size="md"
                  onPress={saveAnswer}
                  disabled={!draft.trim()}
                  loading={submitting}
                >
                  Save
                </Sprout>
              </View>
            </View>
          </View>
        ) : (
          <View style={{ gap: 8 }}>
            {remainingTemplates.map((t) => (
              <Pressable
                key={t.id}
                onPress={() => setActiveTemplateId(t.id)}
                className="bg-surface rounded-2xl border border-border px-4 py-3.5"
              >
                <Text className="font-serif text-foreground" style={{ fontSize: 16, lineHeight: 21 }}>
                  {t.question}
                </Text>
              </Pressable>
            ))}
          </View>
        )}
      </Sheet>

      <Sprout block size="md" onPress={onContinue} disabled={!canContinue}>
        Continue
      </Sprout>
    </View>
  );
}
