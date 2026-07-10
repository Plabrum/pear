// Registered form for `dating_profile_swipe_actions__report` — the two-step
// confirm → reason flow a dater uses to report a profile from the swipe deck.
// Step 1 is a destructive `Dialog`; step 2 is `createTypedForm<ReportActionData>`.
// The registry mounts this fresh per open (keyed on isOpen), so `step` resets.
import { useState } from 'react';

import type { ReportActionData } from '@/lib/api/generated/model';
import { createTypedForm } from '@/lib/forms/typed-form';
import { Dialog } from '@/components/Dialog';

const ReasonForm = createTypedForm<ReportActionData>();

export function ReportReasonForm({
  onSubmit,
  onClose,
  isOpen,
}: {
  objectData?: unknown;
  onSubmit: (data: { reason: string }) => void;
  onClose: () => void;
  isSubmitting: boolean;
  isOpen: boolean;
}) {
  const [step, setStep] = useState<'confirm' | 'reason'>('confirm');
  return (
    <>
      <Dialog
        visible={isOpen && step === 'confirm'}
        onClose={onClose}
        tone="danger"
        title="Report profile?"
        body="Something feel off? Let us know and we'll look into it."
        actions={[
          { label: 'Yes, report', onClick: () => setStep('reason') },
          { label: 'No, cancel', onClick: onClose },
        ]}
      />
      <ReasonForm.FormSheet
        visible={isOpen && step === 'reason'}
        onClose={onClose}
        title="What's the issue?"
        subtitle="Describe the problem so we can review it."
        submitLabel="Send report"
        defaultValues={{ reason: '' }}
        onSubmit={(v) => onSubmit({ reason: v.reason.trim() })}
      >
        <ReasonForm.TextareaField
          name="reason"
          label="What's the issue?"
          placeholder="Describe the problem so we can review it…"
          maxLength={500}
          autoFocus
        />
      </ReasonForm.FormSheet>
    </>
  );
}
