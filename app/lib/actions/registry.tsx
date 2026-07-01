// The action → form registry — ported from sloopquest (lib/actions/registry.tsx).
//
// Sloopquest GENERATES most of this from the action schemas (registry.gen.tsx +
// forms.gen.tsx). Pear has only a couple of data-ful actions, so we register those
// by hand and skip the codegen. Any action NOT in this map has no form and is
// executed directly (data-free) or via a confirmation dialog.
//
// Populated during screen migration:
//   - dating_profile_swipe_actions__suggest → ForwardSheet (collects the note;
//     daterId is injected via the executor's `formContext`)
//   - dating_profile_swipe_actions__report  → ReportSheet (collects the reason)
import type { ReactElement } from 'react';

import { PromptResponseForm } from '@/components/actions/prompt-response-form';
import { ReportReasonForm } from '@/components/actions/report-reason-form';
import { SuggestNoteForm } from '@/components/actions/suggest-note-form';

export interface ActionRegistryEntry {
  /** A self-contained modal/sheet form for the action, or null to skip the form layer. */
  render: (params: {
    objectData?: unknown;
    onSubmit: (data: Record<string, unknown>) => void;
    onClose: () => void;
    isSubmitting: boolean;
    isOpen: boolean;
    actionLabel: string;
  }) => ReactElement | null;
}

export type ActionRegistry = Record<string, ActionRegistryEntry>;

export const actionRegistry: ActionRegistry = {
  // A prompt comment (winger on a dater's profile, or a match on a prompt). The
  // form's `objectData` is the prompt being responded to.
  prompt_response_actions__create: {
    render: (p) => <PromptResponseForm {...p} />,
  },
  // A winger forwarding a profile to a dater; the note is optional, daterId is
  // supplied by the callsite. (The swipe deck collects its note inline instead.)
  dating_profile_swipe_actions__suggest: {
    render: (p) => <SuggestNoteForm {...p} />,
  },
  // Reporting a profile from the swipe deck — a two-step confirm → reason flow.
  // Keyed on isOpen so the internal step resets to `confirm` on each fresh open.
  dating_profile_swipe_actions__report: {
    render: (p) => <ReportReasonForm key={p.isOpen ? 'open' : 'closed'} {...p} />,
  },
};

export function getActionRenderer(actionType: string): ActionRegistryEntry['render'] | undefined {
  return actionRegistry[actionType]?.render;
}
