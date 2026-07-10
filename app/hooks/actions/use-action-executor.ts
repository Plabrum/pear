// Drives every server action: it resolves whether an action needs a form (registry)
// or a confirmation (confirmation_message) or runs directly, executes via the
// generated mutations, then handles the response's message/invalidation/result.
import { useState } from 'react';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useNavigation } from '@react-navigation/native';
import { toast } from 'sonner-native';
import type { ReactNode } from 'react';

import {
  useApiActionsActionGroupExecuteAction,
  useApiActionsActionGroupObjectIdExecuteObjectAction,
} from '@/lib/api/generated/actions/actions';
import { toastError } from '@/lib/api/error-toast';
import { executeActionApi } from './action-executor/execute-action-api';
import { handleActionResult } from './action-executor/handle-action-result';
import { handleQueryInvalidation } from './action-executor/handle-query-invalidation';
import type {
  ActionBodyUnion,
  ActionDTO,
  ActionExecutionResponse,
  ActionGroupType,
} from '@/lib/actions/types';

export type ActionExecutorState = {
  isExecuting: boolean;
  pendingAction: ActionDTO | null;
  showConfirmation: boolean;
  showForm: boolean;
  error: string | null;
};

export type ActionFormRenderer = (props: {
  action: ActionDTO;
  onSubmit: (data: ActionBodyUnion) => void;
  onClose: () => void;
  isSubmitting: boolean;
  isOpen: boolean;
  actionLabel: string;
}) => ReactNode | null;

export type ActionExecutorOptions = {
  actionGroup: ActionGroupType;
  objectId?: string;
  onSuccess?: (action: ActionDTO, response: ActionExecutionResponse) => void;
  onError?: (action: ActionDTO, error: Error) => void;
  renderActionForm?: ActionFormRenderer;
  onInvalidate?: (queryClient: QueryClient, backendQueryKeys: string[]) => void;
  /** Context values merged into every action body (e.g. `{ daterId }` in winger context). */
  formContext?: Record<string, unknown>;
};

export function useActionExecutor({
  actionGroup,
  objectId,
  onSuccess,
  onError,
  renderActionForm,
  onInvalidate,
  formContext,
}: ActionExecutorOptions) {
  const queryClient = useQueryClient();
  const navigation = useNavigation();
  const executeGroupActionMutation = useApiActionsActionGroupExecuteAction();
  const executeObjectActionMutation = useApiActionsActionGroupObjectIdExecuteObjectAction();
  const [state, setState] = useState<ActionExecutorState>({
    isExecuting: false,
    pendingAction: null,
    showConfirmation: false,
    showForm: false,
    error: null,
  });

  /**
   * Run an action. `silent` skips state mutations, the success toast, and post-action
   * navigation — for inline writes (blur saves, drag-drop, swipe) where the dialog
   * flow is noise; error toasts + invalidation still run. `objectId` overrides the
   * executor-level id for per-call object actions (e.g. iterating media/photos).
   */
  async function executeAction(
    action: ActionDTO,
    actionBody?: ActionBodyUnion,
    opts?: { silent?: boolean; objectId?: string }
  ): Promise<ActionExecutionResponse> {
    const silent = opts?.silent ?? false;
    if (!silent) {
      setState((prev) => ({ ...prev, isExecuting: true, error: null }));
    }

    try {
      let finalBody = actionBody;
      if (formContext) {
        const existingData = finalBody ? finalBody.data : {};
        finalBody = {
          action: finalBody ? finalBody.action : action.action,
          data: { ...formContext, ...existingData },
        };
      }

      const response = await executeActionApi({
        action,
        actionGroup,
        objectId: opts?.objectId ?? objectId,
        actionBody: finalBody,
        executeGroupActionMutation,
        executeObjectActionMutation,
      });

      if (!silent) {
        const resultHasOwnToast =
          response.action_result?.type === 'copy_to_clipboard' &&
          response.action_result.toast != null;
        if (!resultHasOwnToast) {
          toast.success(response.message || `${action.label} done`);
        }
      }

      handleQueryInvalidation(queryClient, response, onInvalidate);
      onSuccess?.(action, response);

      if (!silent) {
        handleActionResult(response, navigation);
        setState({
          isExecuting: false,
          pendingAction: null,
          showConfirmation: false,
          showForm: false,
          error: null,
        });
      }

      return response;
    } catch (err) {
      const errorMessage = `Couldn't ${action.label.toLowerCase()}. Please try again.`;
      if (!silent) {
        setState((prev) => ({ ...prev, isExecuting: false, error: errorMessage }));
      }
      toastError(err, errorMessage);
      onError?.(action, err as Error);
      throw err;
    }
  }

  /** True if the action has a registered custom form (so it opens a sheet, not runs directly). */
  function hasCustomForm(action: ActionDTO): boolean {
    if (!renderActionForm) return false;
    return (
      renderActionForm({
        action,
        onSubmit: () => {},
        onClose: () => {},
        isSubmitting: false,
        isOpen: false,
        actionLabel: action.label,
      }) !== null
    );
  }

  /** Entry point from a button: opens a form, asks confirmation, or runs directly. */
  function initiateAction(action: ActionDTO): void {
    if (action.disabled_reason) {
      toast.error(action.disabled_reason.message);
      return;
    }
    if (hasCustomForm(action)) {
      setState((prev) => ({ ...prev, pendingAction: action, showForm: true }));
      return;
    }
    if (action.confirmation_message) {
      setState((prev) => ({ ...prev, pendingAction: action, showConfirmation: true }));
      return;
    }
    executeAction(action).catch((err) => {
      console.error('Action execution failed:', err);
    });
  }

  function confirmAction(): void {
    if (state.pendingAction) executeAction(state.pendingAction);
  }

  function cancelAction(): void {
    setState({
      isExecuting: false,
      pendingAction: null,
      showConfirmation: false,
      showForm: false,
      error: null,
    });
  }

  function executeWithData(data: ActionBodyUnion): void {
    if (state.pendingAction) executeAction(state.pendingAction, data);
  }

  return {
    ...state,
    initiateAction,
    confirmAction,
    cancelAction,
    executeWithData,
    executeAction,
    renderActionForm,
  };
}
