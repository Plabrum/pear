/**
 * Typed action client (actions-native).
 *
 * Every former Hono *write* (POST/PATCH/DELETE) now resolves to a registered
 * backend action executed through the generic action route:
 *
 *   - top-level     POST /api/actions/{action_group}
 *   - object-scoped POST /api/actions/{action_group}/{object_id}
 *
 * The body is a msgspec tagged union: `{ action: "<combined_key>", data: {...} }`.
 * `action` selects the action within the group (the URL's {action_group} must be
 * the prefix of the combined key); `data` is REQUIRED on every action — actions
 * with no payload send `data: {}` (EmptyActionData).
 *
 * Reads stay on the Orval-generated `useGetApi*Suspense` hooks — this module only
 * covers mutations. We call the generated `apiActionsActionGroup*ExecuteAction`
 * functions directly (they go through `pearFetch`, attaching the JWT and throwing
 * on a non-2xx) and wrap each former mutation in a typed helper so callsites read
 * intent, not transport.
 *
 * Returns: every action resolves to `ActionExecutionResponse`
 *   { message, invalidate_queries, action_result, created_id }.
 * Create-style actions carry the new row id in `created_id`; decision actions use
 * `created_id` as the match id (non-null => a mutual match was just formed).
 *
 * NOTE: `POST /api/photos/upload-url` stayed a dedicated route (it is NOT an
 * action). `getPhotoUploadUrl` re-exports the generated function so all photo
 * writes import from one place.
 */
import {
  apiActionsActionGroupExecuteAction,
  apiActionsActionGroupObjectIdExecuteObjectAction,
} from '@/lib/api/generated/actions/actions';
import { postApiPhotosUploadUrl } from '@/lib/api/generated/photos/photos';
import type {
  ActionExecutionResponse,
  CreateDatingProfileData,
  CreatePhotoData,
  CreateProfilePromptData,
  CreatePromptResponseData,
  CreateReportData,
  DirectDecisionData,
  ActSuggestionData,
  SuggestData,
  InviteWingpersonData,
  PhotoUploadUrlData,
  PhotoUploadUrlResponse,
  ReorderPhotoData,
  SendMessageData,
  UpdateDatingProfileData,
  UpdateProfileData,
} from '@/lib/api/generated/model';

// Empty payload for actions that take no `data` — `data` is a required field on
// every action struct, so no-body actions still send `{}`.
const EMPTY = {} as const;

// ── profile_actions ──────────────────────────────────────────────────────────

/**
 * Former `PATCH /api/profiles/me`. Now object-scoped: pass the caller's own
 * profile id (Profile.id === userId), which was implicit (`/me`) before.
 */
export function updateMyProfile(
  profileId: string,
  data: UpdateProfileData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('profile_actions', profileId, {
    action: 'profile_actions__update',
    data,
  });
}

// ── dating_profile_actions ───────────────────────────────────────────────────

/**
 * Former `POST /api/dating-profiles`. Top-level. The new dating-profile id comes
 * back in `created_id`.
 */
export function createDatingProfile(
  data: CreateDatingProfileData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('dating_profile_actions', {
    action: 'dating_profile_actions__create',
    data,
  });
}

/**
 * Former `PATCH /api/dating-profiles/me`. Now object-scoped: pass the caller's
 * own dating-profile id (OwnDatingProfile.id).
 */
export function updateDatingProfile(
  datingProfileId: string,
  data: UpdateDatingProfileData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction(
    'dating_profile_actions',
    datingProfileId,
    { action: 'dating_profile_actions__update', data }
  );
}

// ── decision_actions ─────────────────────────────────────────────────────────

/**
 * Former `POST /api/decisions` (a dater's direct like/pass). Top-level. On a
 * mutual approval the backend forms a match and returns its id in `created_id`
 * (non-null => "it's a match").
 */
export function decide(data: DirectDecisionData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('decision_actions', {
    action: 'decision_actions__record',
    data,
  });
}

/**
 * Former `POST /api/decisions/suggestions` (a winger suggests a profile for a
 * dater). Top-level. `decision: null` = normal suggestion; `decision: 'declined'`
 * = bypass the dater.
 */
export function suggestDecision(data: SuggestData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('decision_actions', {
    action: 'decision_actions__create_suggestion',
    data,
  });
}

/**
 * Former `POST /api/decisions/suggestions/act` (a dater acts on a winger's
 * pending suggestion). Top-level. A resulting match id comes back in `created_id`.
 */
export function actOnSuggestion(data: ActSuggestionData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('decision_actions', {
    action: 'decision_actions__act_suggestion',
    data,
  });
}

// ── photo_actions ────────────────────────────────────────────────────────────

/** Former `POST /api/photos` (write the profile_photos metadata row). Top-level. */
export function addPhoto(data: CreatePhotoData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('photo_actions', {
    action: 'photo_actions__create',
    data,
  });
}

/**
 * Former `POST /api/photos/upload-url`. This stayed a dedicated route (NOT an
 * action) — re-exported here so every photo write lives in one module.
 */
export function getPhotoUploadUrl(data: PhotoUploadUrlData): Promise<PhotoUploadUrlResponse> {
  return postApiPhotosUploadUrl(data);
}

/** Former `POST /api/photos/{id}/approve`. Object-scoped (photo id). */
export function approvePhoto(photoId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('photo_actions', photoId, {
    action: 'photo_actions__approve',
    data: EMPTY,
  });
}

/** Former `POST /api/photos/{id}/reject`. Object-scoped (photo id). */
export function rejectPhoto(photoId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('photo_actions', photoId, {
    action: 'photo_actions__reject',
    data: EMPTY,
  });
}

/** Former `PATCH /api/photos/{id}/reorder`. Object-scoped (photo id). */
export function reorderPhoto(
  photoId: string,
  data: ReorderPhotoData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('photo_actions', photoId, {
    action: 'photo_actions__reorder',
    data,
  });
}

/** Former `DELETE /api/photos/{id}`. Object-scoped (photo id). */
export function deletePhoto(photoId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('photo_actions', photoId, {
    action: 'photo_actions__delete',
    data: EMPTY,
  });
}

// ── profile_prompt_actions ───────────────────────────────────────────────────

/** Former `POST /api/profile-prompts`. Top-level. New row id in `created_id`. */
export function addProfilePrompt(data: CreateProfilePromptData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('profile_prompt_actions', {
    action: 'profile_prompt_actions__create',
    data,
  });
}

/** Former `DELETE /api/profile-prompts/{id}`. Object-scoped (profile_prompt id). */
export function deleteProfilePrompt(promptId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('profile_prompt_actions', promptId, {
    action: 'profile_prompt_actions__delete',
    data: EMPTY,
  });
}

// ── prompt_response_actions ──────────────────────────────────────────────────

/** Former `POST /api/prompt-responses`. Top-level. New row id in `created_id`. */
export function addPromptResponse(
  data: CreatePromptResponseData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('prompt_response_actions', {
    action: 'prompt_response_actions__create',
    data,
  });
}

/** Former `POST /api/prompt-responses/{id}/approve`. Object-scoped (response id). */
export function approvePromptResponse(responseId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('prompt_response_actions', responseId, {
    action: 'prompt_response_actions__approve',
    data: EMPTY,
  });
}

/** Former `DELETE /api/prompt-responses/{id}`. Object-scoped (response id). */
export function deletePromptResponse(responseId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('prompt_response_actions', responseId, {
    action: 'prompt_response_actions__delete',
    data: EMPTY,
  });
}

// ── report_actions ───────────────────────────────────────────────────────────

/** Former `POST /api/reports`. Top-level. */
export function reportProfile(data: CreateReportData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('report_actions', {
    action: 'report_actions__file',
    data,
  });
}

// ── contact_actions ──────────────────────────────────────────────────────────

/** Former `POST /api/wingpeople/invite`. Top-level. New contact id in `created_id`. */
export function inviteWingperson(data: InviteWingpersonData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('contact_actions', {
    action: 'contact_actions__invite',
    data,
  });
}

/** Former `POST /api/wingpeople/{id}/accept`. Object-scoped (contact id). */
export function acceptWingperson(contactId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('contact_actions', contactId, {
    action: 'contact_actions__accept',
    data: EMPTY,
  });
}

/** Former `POST /api/wingpeople/{id}/decline`. Object-scoped (contact id). */
export function declineWingperson(contactId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('contact_actions', contactId, {
    action: 'contact_actions__decline',
    data: EMPTY,
  });
}

/** Former `DELETE /api/wingpeople/{id}`. Object-scoped (contact id). */
export function removeWingperson(contactId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('contact_actions', contactId, {
    action: 'contact_actions__remove',
    data: EMPTY,
  });
}

// ── message_actions ──────────────────────────────────────────────────────────

/**
 * Former `POST /api/matches/{matchId}/messages`. Object-scoped on the MATCH id
 * (the message-actions group's model_type is Match). New message id in `created_id`.
 */
export function sendMessage(
  matchId: string,
  data: SendMessageData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('message_actions', matchId, {
    action: 'message_actions__send',
    data,
  });
}

/**
 * Former `POST /api/matches/{matchId}/messages/read`. Object-scoped on the MATCH id.
 */
export function markMessagesRead(matchId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('message_actions', matchId, {
    action: 'message_actions__mark_read',
    data: EMPTY,
  });
}
