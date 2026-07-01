// Registered form for `dating_profile_swipe_actions__suggest` — the optional note a
// winger attaches when forwarding a profile to one of their daters. Built on
// `createTypedForm<SuggestActionData>` (Sheet presentation). `objectData` carries the
// names for the copy; `daterId` is injected by the executor's `formContext` (or by
// the callsite body), so the form collects only `note`.
import type { SuggestActionData } from '@/lib/api/generated/model';
import { createTypedForm } from '@/lib/forms/typed-form';

const SuggestForm = createTypedForm<SuggestActionData>();

type SuggestContext = { daterFirstName?: string; subjectName?: string };

export function SuggestNoteForm({
  objectData,
  onSubmit,
  onClose,
  isOpen,
}: {
  objectData?: unknown;
  onSubmit: (data: { note: string | null }) => void;
  onClose: () => void;
  isSubmitting: boolean;
  isOpen: boolean;
}) {
  const ctx = objectData as SuggestContext | undefined;
  const daterFirst = ctx?.daterFirstName?.trim() || 'them';
  const subject = ctx?.subjectName?.trim() || 'they';
  return (
    <SuggestForm.FormSheet
      visible={isOpen}
      onClose={onClose}
      title={`Suggest to ${daterFirst}`}
      subtitle={`Send ${subject} over with an optional note.`}
      submitLabel="Suggest"
      defaultValues={{ note: '' }}
      onSubmit={(v) => onSubmit({ note: v.note?.trim() ? v.note.trim() : null })}
    >
      <SuggestForm.TextareaField
        name="note"
        label="Note"
        optional
        maxLength={240}
        placeholder="Why are they a good match?"
        autoFocus
      />
    </SuggestForm.FormSheet>
  );
}
