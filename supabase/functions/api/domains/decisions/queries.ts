import { and, desc, eq, inArray, isNotNull, isNull, sql } from 'drizzle-orm';
import type { DBOrTx } from '../../db/client.ts';
import { contacts, decisions, matches, profiles } from '../../db/schema.ts';
import type { MatchRow, PendingSuggestionRow } from './transformers.ts';

export type DirectDecision = 'approved' | 'declined';

// Direct like/pass: upsert the actor's decision on the recipient. The
// `create_match_if_mutual` DB trigger fires after insert/update and creates a
// matches row when both directions are 'approved'.
export async function upsertDirectDecision(
  db: DBOrTx,
  actorId: string,
  recipientId: string,
  decision: DirectDecision,
): Promise<void> {
  await db
    .insert(decisions)
    .values({ actorId, recipientId, decision })
    .onConflictDoUpdate({
      target: [decisions.actorId, decisions.recipientId],
      set: { decision },
    });
}

// Approve/decline a winger's pending suggestion. Constrained to rows the
// caller actually owns (actor_id) AND where decision IS NULL so we can't
// overwrite a finalised decision through this endpoint.
export async function actOnPendingSuggestion(
  db: DBOrTx,
  actorId: string,
  recipientId: string,
  decision: DirectDecision,
): Promise<{ updated: boolean }> {
  const rows = await db
    .update(decisions)
    .set({ decision })
    .where(
      and(
        eq(decisions.actorId, actorId),
        eq(decisions.recipientId, recipientId),
        isNull(decisions.decision),
      ),
    )
    .returning({ id: decisions.id });
  return { updated: rows.length > 0 };
}

// Winger creates a suggestion row on the dater's behalf. `decision`:
//   • null     → normal suggestion the dater can act on (with optional note).
//   • 'declined' → winger declines the recipient on the dater's behalf;
//                  bypasses the dater's feed entirely.
export async function insertWingSuggestion(
  db: DBOrTx,
  daterId: string,
  recipientId: string,
  wingerId: string,
  note: string | null,
  decision: 'declined' | null,
): Promise<void> {
  await db
    .insert(decisions)
    .values({
      actorId: daterId,
      recipientId,
      suggestedBy: wingerId,
      decision,
      note,
    })
    .onConflictDoNothing();
}

// Look up the matches row for a pair, regardless of who is user_a vs user_b.
// `matches` enforces user_a_id < user_b_id, so we order before querying.
export async function findMutualMatch(
  db: DBOrTx,
  userA: string,
  userB: string,
): Promise<MatchRow | null> {
  const a = userA < userB ? userA : userB;
  const b = userA < userB ? userB : userA;
  const [row] = await db
    .select({
      id: matches.id,
      user_a_id: matches.userAId,
      user_b_id: matches.userBId,
      created_at: matches.createdAt,
    })
    .from(matches)
    .where(and(eq(matches.userAId, a), eq(matches.userBId, b)))
    .limit(1);
  return row ?? null;
}

export async function isActiveWingperson(
  db: DBOrTx,
  daterId: string,
  wingerId: string,
): Promise<boolean> {
  const [row] = await db
    .select({ one: sql<number>`1` })
    .from(contacts)
    .where(
      and(
        eq(contacts.userId, daterId),
        eq(contacts.wingerId, wingerId),
        eq(contacts.wingpersonStatus, 'active'),
      ),
    )
    .limit(1);
  return row != null;
}

export async function getPushTokensFor(
  db: DBOrTx,
  userIds: string[],
): Promise<Array<{ id: string; pushToken: string | null }>> {
  if (userIds.length === 0) return [];
  const rows = await db
    .select({ id: profiles.id, pushToken: profiles.pushToken })
    .from(profiles)
    .where(inArray(profiles.id, userIds));
  return rows;
}

export async function getDaterPushAndWingerName(
  db: DBOrTx,
  daterId: string,
  wingerId: string,
): Promise<{ daterToken: string | null; wingerName: string | null }> {
  const rows = await db
    .select({
      id: profiles.id,
      pushToken: profiles.pushToken,
      chosenName: profiles.chosenName,
    })
    .from(profiles)
    .where(inArray(profiles.id, [daterId, wingerId]));

  const dater = rows.find((r) => r.id === daterId);
  const winger = rows.find((r) => r.id === wingerId);
  return {
    daterToken: dater?.pushToken ?? null,
    wingerName: winger?.chosenName ?? null,
  };
}

export async function fetchPendingSuggestions(
  db: DBOrTx,
  actorId: string,
): Promise<PendingSuggestionRow[]> {
  const rows = await db
    .select({
      id: decisions.id,
      recipient_id: decisions.recipientId,
      note: decisions.note,
      created_at: decisions.createdAt,
      winger_id: decisions.suggestedBy,
      winger_name: profiles.chosenName,
    })
    .from(decisions)
    .leftJoin(profiles, eq(profiles.id, decisions.suggestedBy))
    .where(
      and(
        eq(decisions.actorId, actorId),
        isNull(decisions.decision),
        isNotNull(decisions.suggestedBy),
      ),
    )
    .orderBy(desc(decisions.createdAt));

  return rows as PendingSuggestionRow[];
}
