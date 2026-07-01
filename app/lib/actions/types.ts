// The executor + registry import from here so the rest of the app has one
// stable action vocabulary.
import type { ActionDTO, ActionGroupType } from '@/lib/api/generated/model';

export type { ActionDTO, ActionGroupType } from '@/lib/api/generated/model';
export type {
  ActionExecutionResponse,
  DisabledReason,
  ActionCTA,
} from '@/lib/api/generated/model';

// The `{ action, data }` body the action routes accept. The generated client types
// `data` as a big discriminated union; the executor builds bodies dynamically and
// casts at the mutation boundary, so a loose shape is enough here.
export type ActionBodyUnion = { action: string; data: Record<string, unknown> };

/** The short action key — the suffix after `<group>__` (e.g. "accept", "remove"). */
export function shortKey(action: string): string {
  const i = action.indexOf('__');
  return i === -1 ? action : action.slice(i + 2);
}

/** Object-level actions — performed on a specific object instance (its row carries actions[]). */
export interface ObjectActionData {
  data: { id: string; actions?: ActionDTO[] | null };
  actionGroup: ActionGroupType;
  onRefetch?: () => void;
  onActionComplete?: (action: ActionDTO, response: unknown) => void;
}

/** Top-level actions — not tied to an object (e.g. "Invite wingperson"). */
export interface TopLevelActionData {
  actions?: ActionDTO[] | null;
  actionGroup: ActionGroupType;
  onInvalidate?: () => void;
  onActionComplete?: (action: ActionDTO, response: unknown) => void;
}
