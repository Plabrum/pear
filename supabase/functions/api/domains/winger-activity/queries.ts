import { and, desc, eq, isNotNull, sql } from 'drizzle-orm';
import { alias } from 'drizzle-orm/pg-core';
import type { DBOrTx } from '../../db/client.ts';
import {
  datingProfiles,
  decisions,
  matches,
  profiles,
  profilePhotos,
  profilePrompts,
  promptResponses,
  promptTemplates,
} from '../../db/schema.ts';

export type SuggestionRow = {
  id: string;
  decision: 'approved' | 'declined' | null;
  has_match: boolean;
  dater_id: string;
  dater_name: string;
  recipient_name: string;
  created_at: string;
};

export type PhotoRow = {
  id: string;
  dater_id: string;
  dater_name: string;
  storage_url: string;
  approved_at: string | null;
  rejected_at: string | null;
  created_at: string;
};

export type PromptRow = {
  id: string;
  dater_id: string;
  dater_name: string;
  prompt_question: string;
  message: string;
  is_approved: boolean;
  is_rejected: boolean;
  created_at: string;
};

export async function fetchPeopleActivity(
  db: DBOrTx,
  wingerId: string,
  limit: number,
): Promise<SuggestionRow[]> {
  const dater = alias(profiles, 'dater');
  const recipient = alias(profiles, 'recipient');

  const matchExistsExpr = sql<boolean>`exists (
    select 1 from ${matches}
    where (${matches.userAId} = ${decisions.actorId} and ${matches.userBId} = ${decisions.recipientId})
       or (${matches.userAId} = ${decisions.recipientId} and ${matches.userBId} = ${decisions.actorId})
  )`;

  const rows = await db
    .select({
      id: decisions.id,
      decision: decisions.decision,
      has_match: matchExistsExpr.as('has_match'),
      dater_id: decisions.actorId,
      dater_name: dater.chosenName,
      recipient_name: recipient.chosenName,
      created_at: decisions.createdAt,
    })
    .from(decisions)
    .innerJoin(dater, eq(dater.id, decisions.actorId))
    .innerJoin(recipient, eq(recipient.id, decisions.recipientId))
    .where(and(isNotNull(decisions.suggestedBy), eq(decisions.suggestedBy, wingerId)))
    .orderBy(desc(decisions.createdAt))
    .limit(limit);

  return rows as SuggestionRow[];
}

export async function fetchPhotosActivity(
  db: DBOrTx,
  wingerId: string,
  limit: number,
): Promise<PhotoRow[]> {
  const rows = await db
    .select({
      id: profilePhotos.id,
      dater_id: datingProfiles.userId,
      dater_name: profiles.chosenName,
      storage_url: profilePhotos.storageUrl,
      approved_at: profilePhotos.approvedAt,
      rejected_at: profilePhotos.rejectedAt,
      created_at: profilePhotos.createdAt,
    })
    .from(profilePhotos)
    .innerJoin(datingProfiles, eq(datingProfiles.id, profilePhotos.datingProfileId))
    .innerJoin(profiles, eq(profiles.id, datingProfiles.userId))
    .where(eq(profilePhotos.suggesterId, wingerId))
    .orderBy(desc(profilePhotos.createdAt))
    .limit(limit);

  return rows as PhotoRow[];
}

export async function fetchPromptsActivity(
  db: DBOrTx,
  wingerId: string,
  limit: number,
): Promise<PromptRow[]> {
  const rows = await db
    .select({
      id: promptResponses.id,
      dater_id: datingProfiles.userId,
      dater_name: profiles.chosenName,
      prompt_question: promptTemplates.question,
      message: promptResponses.message,
      is_approved: promptResponses.isApproved,
      is_rejected: promptResponses.isRejected,
      created_at: promptResponses.createdAt,
    })
    .from(promptResponses)
    .innerJoin(profilePrompts, eq(profilePrompts.id, promptResponses.profilePromptId))
    .innerJoin(promptTemplates, eq(promptTemplates.id, profilePrompts.promptTemplateId))
    .innerJoin(datingProfiles, eq(datingProfiles.id, profilePrompts.datingProfileId))
    .innerJoin(profiles, eq(profiles.id, datingProfiles.userId))
    .where(eq(promptResponses.userId, wingerId))
    .orderBy(desc(promptResponses.createdAt))
    .limit(limit);

  return rows as PromptRow[];
}
