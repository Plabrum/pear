// Registered form for `dating_profile_swipe_actions__suggest` — the optional note a
// winger attaches when forwarding a profile to one of their daters. Wraps the
// existing NoteModal so the look is unchanged; `objectData` carries the names for
// the copy. `daterId` is supplied by the callsite (the picked dater), not here.
import { NoteModal } from '@/components/ui/NoteModal';

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
  return (
    <NoteModal
      visible={isOpen}
      daterFirstName={ctx?.daterFirstName ?? ''}
      subjectName={ctx?.subjectName ?? 'they'}
      onSend={(note) => onSubmit({ note })}
      onDismiss={onClose}
    />
  );
}
