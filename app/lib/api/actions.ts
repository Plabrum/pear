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
// Create-style actions carry the new row id in `created_id`; a like that forms a
// mutual match returns the match id in `created_id` (non-null => "it's a pear").
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
  SuggestActionData,
  DeclineForDaterData,
  ReportActionData,
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

/**
 * Switch the caller into winger mode ("just winging"). Object-scoped: pass the
 * caller's own profile id (Profile.id === userId). Their dating profile is kept but
 * hidden from feeds while role === winger.
 */
export function switchToWinger(profileId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('profile_actions', profileId, {
    action: 'profile_actions__switch_to_winger',
    data: EMPTY,
  });
}

/**
 * Switch the caller back into dater mode (start / resume dating). Object-scoped:
 * pass the caller's own profile id (Profile.id === userId).
 */
export function switchToDater(profileId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction('profile_actions', profileId, {
    action: 'profile_actions__switch_to_dater',
    data: EMPTY,
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

/**
 * Pause dating (take a break). Object-scoped: pass the caller's own dating-profile
 * id (OwnDatingProfile.id). Moves dating status OPEN -> BREAK.
 */
export function pauseDating(datingProfileId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction(
    'dating_profile_actions',
    datingProfileId,
    { action: 'dating_profile_actions__pause', data: EMPTY }
  );
}

/**
 * Resume dating. Object-scoped: pass the caller's own dating-profile id
 * (OwnDatingProfile.id). Moves dating status BREAK -> OPEN.
 */
export function resumeDating(datingProfileId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction(
    'dating_profile_actions',
    datingProfileId,
    { action: 'dating_profile_actions__resume', data: EMPTY }
  );
}

// ── dating_profile_swipe_actions ─────────────────────────────────────────────
// All swipe writes target the DatingProfile being acted on. Object-scoped: pass
// the SwipeProfile.profileId (the dating-profile id, NOT the user id). Like/pass
// cover both the dater's direct decisions and acting on a winger's suggestion.

/**
 * Like a profile. On a mutual approval the backend forms a match and returns its
 * id in `created_id` (non-null => "it's a match").
 */
export function like(datingProfileId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction(
    'dating_profile_swipe_actions',
    datingProfileId,
    { action: 'dating_profile_swipe_actions__like', data: EMPTY }
  );
}

/** Pass on a profile. */
export function pass(datingProfileId: string): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction(
    'dating_profile_swipe_actions',
    datingProfileId,
    { action: 'dating_profile_swipe_actions__pass', data: EMPTY }
  );
}

/**
 * A winger proposes this profile to one of their daters — a pending suggestion the
 * dater must act on. `daterId` is required; `note` is an optional hand-pick note.
 */
export function suggest(
  datingProfileId: string,
  data: SuggestActionData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction(
    'dating_profile_swipe_actions',
    datingProfileId,
    { action: 'dating_profile_swipe_actions__suggest', data }
  );
}

/**
 * A winger passes on this profile on the dater's behalf — records a decline so it
 * leaves the dater's pool; the dater is not notified. `daterId` is required.
 */
export function declineForDater(
  datingProfileId: string,
  data: DeclineForDaterData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction(
    'dating_profile_swipe_actions',
    datingProfileId,
    { action: 'dating_profile_swipe_actions__decline', data }
  );
}

/** File a report against this profile. `reason` is required. */
export function report(
  datingProfileId: string,
  data: ReportActionData
): Promise<ActionExecutionResponse> {
  return apiActionsActionGroupObjectIdExecuteObjectAction(
    'dating_profile_swipe_actions',
    datingProfileId,
    { action: 'dating_profile_swipe_actions__report', data }
  );
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
