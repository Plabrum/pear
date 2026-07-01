// Registered form for `prompt_response_actions__create` — a winger/match comment on
// a dater's prompt. Built on `createTypedForm<CreatePromptResponseData>` (Sheet
// presentation). `objectData` is the prompt being responded to; its id supplies
// `profilePromptId`, so the form collects only `message`.
import type { CreatePromptResponseData } from '@/lib/api/generated/model';
import { createTypedForm } from '@/lib/forms/typed-form';

const ResponseForm = createTypedForm<CreatePromptResponseData>();

type PromptContext = { id: string; question?: string | null };

export function PromptResponseForm({
  objectData,
  onSubmit,
  onClose,
  isOpen,
}: {
  objectData?: unknown;
  onSubmit: (data: { profilePromptId: string; message: string }) => void;
  onClose: () => void;
  isSubmitting: boolean;
  isOpen: boolean;
}) {
  const prompt = objectData as PromptContext | undefined;
  if (!prompt) return null;
  return (
    <ResponseForm.FormSheet
      visible={isOpen}
      onClose={onClose}
      title="Add a comment"
      subtitle={prompt.question ?? undefined}
      submitLabel="Send comment"
      defaultValues={{ message: '' }}
      onSubmit={(v) => onSubmit({ profilePromptId: prompt.id, message: v.message.trim() })}
    >
      <ResponseForm.TextareaField
        name="message"
        label="Comment"
        placeholder="Write a comment on this prompt…"
        maxLength={300}
        autoFocus
      />
    </ResponseForm.FormSheet>
  );
}
