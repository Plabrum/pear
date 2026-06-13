import type { PeopleActivityRow, PhotoActivityRow, PromptActivityRow } from './schemas.ts';
import type { SuggestionRow, PhotoRow, PromptRow } from './queries.ts';

export function transformSuggestion(row: SuggestionRow): PeopleActivityRow {
  const status: PeopleActivityRow['status'] =
    row.decision === 'declined'
      ? 'not_accepted'
      : row.decision === 'approved' && row.has_match
        ? 'matched'
        : 'pending';
  return {
    id: `suggestion:${row.id}`,
    daterId: row.dater_id,
    daterName: row.dater_name,
    suggestedName: row.recipient_name,
    status,
    createdAt: row.created_at,
  };
}

export function transformPhoto(row: PhotoRow): PhotoActivityRow {
  const status: PhotoActivityRow['status'] = row.rejected_at
    ? 'not_accepted'
    : row.approved_at
      ? 'approved'
      : 'pending';
  return {
    id: row.id,
    daterId: row.dater_id,
    daterName: row.dater_name,
    storageUrl: row.storage_url,
    status,
    createdAt: row.created_at,
  };
}

export function transformPrompt(row: PromptRow): PromptActivityRow {
  const status: PromptActivityRow['status'] = row.is_rejected
    ? 'not_accepted'
    : row.is_approved
      ? 'accepted'
      : 'pending';
  return {
    id: row.id,
    daterId: row.dater_id,
    daterName: row.dater_name,
    promptQuestion: row.prompt_question,
    message: row.message,
    status,
    createdAt: row.created_at,
  };
}
