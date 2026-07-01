import type {
  useApiActionsActionGroupExecuteAction,
  useApiActionsActionGroupObjectIdExecuteObjectAction,
} from '@/lib/api/generated/actions/actions';
import type {
  ActionBodyUnion,
  ActionDTO,
  ActionExecutionResponse,
  ActionGroupType,
} from '@/lib/actions/types';

// The orval-generated mutation hooks; their `mutateAsync` takes
// `{ actionGroup, data }` / `{ actionGroup, objectId, data }` where `data` is the
// big discriminated action union. We build bodies dynamically, so cast at the call.
type GroupMutation = ReturnType<typeof useApiActionsActionGroupExecuteAction>;
type ObjectMutation = ReturnType<typeof useApiActionsActionGroupObjectIdExecuteObjectAction>;

type ExecuteActionApiParams = {
  action: ActionDTO;
  actionGroup: ActionGroupType;
  objectId?: string;
  actionBody?: ActionBodyUnion;
  executeGroupActionMutation: GroupMutation;
  executeObjectActionMutation: ObjectMutation;
};

/** Dispatch a group-level or object-level action through the right generated mutation. */
export async function executeActionApi({
  action,
  actionGroup,
  objectId,
  actionBody,
  executeGroupActionMutation,
  executeObjectActionMutation,
}: ExecuteActionApiParams): Promise<ActionExecutionResponse> {
  const requestBody: ActionBodyUnion = actionBody ?? { action: action.action, data: {} };

  if (objectId) {
    return executeObjectActionMutation.mutateAsync({
      actionGroup,
      objectId,
      data: requestBody as never,
    });
  }
  return executeGroupActionMutation.mutateAsync({ actionGroup, data: requestBody as never });
}
