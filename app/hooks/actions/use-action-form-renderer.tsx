// Bridges the action registry to the executor's `renderActionForm` — ported from
// sloopquest. Looks up the registered form for an action; returns null (→ execute
// directly) when there's no form. The `onSubmit` wraps the form's data into the
// `{ action, data }` body the executor expects.
import { useCallback } from 'react';

import { getActionRenderer } from '@/lib/actions/registry';
import type { ActionFormRenderer } from './use-action-executor';

export function useActionFormRenderer(objectData?: unknown): ActionFormRenderer {
  return useCallback<ActionFormRenderer>(
    ({ action, onSubmit, onClose, isSubmitting, isOpen, actionLabel }) => {
      const render = getActionRenderer(action.action);
      if (!render) return null;
      return render({
        objectData,
        onSubmit: (data) => onSubmit({ action: action.action, data }),
        onClose,
        isSubmitting,
        isOpen,
        actionLabel,
      });
    },
    [objectData]
  );
}
