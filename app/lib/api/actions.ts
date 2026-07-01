// Typed action client. Every write (POST/PATCH/DELETE) resolves to a registered
// backend action executed through the generic action route:
//
//   - top-level     POST /api/actions/{action_group}
//   - object-scoped POST /api/actions/{action_group}/{object_id}
//
// The body is a msgspec tagged union: `{ action: "<combined_key>", data: {...} }`.
// `action` selects the action within the group (the URL's {action_group} must be
// the prefix of the combined key); `data` is REQUIRED on every action — actions
// with no payload send `data: {}` (EmptyActionData).
//
// Reads stay on the Orval-generated `useGetApi*Suspense` hooks — this module only
// covers mutations. We call the generated `apiActionsActionGroup*ExecuteAction`
// functions directly (they go through `pearFetch`, attaching the JWT and throwing
// on a non-2xx) and wrap each mutation in a typed helper so callsites read
// intent, not transport.
//
// Every action resolves to `ActionExecutionResponse`
//   { message, invalidate_queries, action_result, created_id }.
// Create-style actions carry the new row id in `created_id`; decision actions use
// `created_id` as the match id (non-null => a mutual match was just formed).
//
// NOTE: Image uploads do NOT go through actions. They use the media domain's
// dedicated routes (`POST /api/media/upload-url` -> PUT bytes -> `POST
// /api/media/{id}/uploaded`) in `lib/photos.ts`, which yields a media id that
// photo/avatar writes here pin to a row (`mediaId` / `avatarMediaId`).
import {
  apiActionsActionGroupExecuteAction,
  apiActionsActionGroupObjectIdExecuteObjectAction,
} from '@/lib/api/generated/actions/actions';
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
 * Update the caller's own profile. Object-scoped: pass the caller's own profile
 * id (Profile.id === userId).
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
 * Create the caller's dating profile. Top-level. The new dating-profile id comes
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
 * Update the caller's dating profile. Object-scoped: pass the caller's own
 * dating-profile id (OwnDatingProfile.id).
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
 * Record a dater's direct like/pass. Top-level. On a mutual approval the backend
 * forms a match and returns its id in `created_id` (non-null => "it's a match").
 */
export function decide(data: DirectDecisionData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('decision_actions', {
    action: 'decision_actions__record',
    data,
  });
}

/**
 * A winger suggests a profile for a dater. Top-level. `decision: null` = normal
 * suggestion; `decision: 'declined'` = bypass the dater.
 */
export function suggestDecision(data: SuggestData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('decision_actions', {
    action: 'decision_actions__create_suggestion',
    data,
  });
}

/**
 * A dater acts on a winger's pending suggestion. Top-level. A resulting match id
 * comes back in `created_id`.
 */
export function actOnSuggestion(data: ActSuggestionData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('decision_actions', {
    action: 'decision_actions__act_suggestion',
    data,
  });
}

// ── photo_actions ────────────────────────────────────────────────────────────

/** Write the profile_photos metadata row. Top-level. */
export function addPhoto(data: CreatePhotoData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('photo_actions', {
    action: 'photo_actions__create',
    data,
  });
}

/** Approve a photo. Object-scoped (photo id). */
export function approvePhoto(photoId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('photo_actions', photoId, {
    action: 'photo_actions__approve',
    data: EMPTY,
  });
}

/** Reject a photo. Object-scoped (photo id). */
export function rejectPhoto(photoId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('photo_actions', photoId, {
    action: 'photo_actions__reject',
    data: EMPTY,
  });
}

/** Reorder a photo. Object-scoped (photo id). */
export function reorderPhoto(
  photoId: string,
  data: ReorderPhotoData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('photo_actions', photoId, {
    action: 'photo_actions__reorder',
    data,
  });
}

/** Delete a photo. Object-scoped (photo id). */
export function deletePhoto(photoId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('photo_actions', photoId, {
    action: 'photo_actions__delete',
    data: EMPTY,
  });
}

// ── profile_prompt_actions ───────────────────────────────────────────────────

/** Add a profile prompt. Top-level. New row id in `created_id`. */
export function addProfilePrompt(data: CreateProfilePromptData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('profile_prompt_actions', {
    action: 'profile_prompt_actions__create',
    data,
  });
}

/** Delete a profile prompt. Object-scoped (profile_prompt id). */
export function deleteProfilePrompt(promptId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('profile_prompt_actions', promptId, {
    action: 'profile_prompt_actions__delete',
    data: EMPTY,
  });
}

// ── prompt_response_actions ──────────────────────────────────────────────────

/** Add a prompt response. Top-level. New row id in `created_id`. */
export function addPromptResponse(
  data: CreatePromptResponseData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('prompt_response_actions', {
    action: 'prompt_response_actions__create',
    data,
  });
}

/** Approve a prompt response. Object-scoped (response id). */
export function approvePromptResponse(responseId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('prompt_response_actions', responseId, {
    action: 'prompt_response_actions__approve',
    data: EMPTY,
  });
}

/** Delete a prompt response. Object-scoped (response id). */
export function deletePromptResponse(responseId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('prompt_response_actions', responseId, {
    action: 'prompt_response_actions__delete',
    data: EMPTY,
  });
}

// ── report_actions ───────────────────────────────────────────────────────────

/** File a report against a profile. Top-level. */
export function reportProfile(data: CreateReportData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('report_actions', {
    action: 'report_actions__file',
    data,
  });
}

// ── contact_actions ──────────────────────────────────────────────────────────

/** Invite a wingperson. Top-level. New contact id in `created_id`. */
export function inviteWingperson(data: InviteWingpersonData): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupExecuteAction('contact_actions', {
    action: 'contact_actions__invite',
    data,
  });
}

/** Accept a wingperson invite. Object-scoped (contact id). */
export function acceptWingperson(contactId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('contact_actions', contactId, {
    action: 'contact_actions__accept',
    data: EMPTY,
  });
}

/** Decline a wingperson invite. Object-scoped (contact id). */
export function declineWingperson(contactId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('contact_actions', contactId, {
    action: 'contact_actions__decline',
    data: EMPTY,
  });
}

/** Remove a wingperson. Object-scoped (contact id). */
export function removeWingperson(contactId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('contact_actions', contactId, {
    action: 'contact_actions__remove',
    data: EMPTY,
  });
}

// ── message_actions ──────────────────────────────────────────────────────────

/**
 * Send a message. Object-scoped on the MATCH id (the message-actions group's
 * model_type is Match). New message id in `created_id`.
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

/** Mark a match's messages as read. Object-scoped on the MATCH id. */
export function markMessagesRead(matchId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('message_actions', matchId, {
    action: 'message_actions__mark_read',
    data: EMPTY,
  });
}
