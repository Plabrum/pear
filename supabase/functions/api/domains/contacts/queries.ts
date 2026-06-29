import { and, asc, desc, eq, gte, inArray } from 'drizzle-orm';
import type { DBOrTx } from '../../db/client.ts';
import { contacts, datingProfiles, decisions, profiles } from '../../db/schema.ts';
import type {
  IncomingInvitationRow,
  SentInvitationRow,
  WingingForDaterRow,
  WingpersonRow,
} from './transformers.ts';

export async function fetchPushToken(db: DBOrTx, userId: string): Promise<string | null> {
  const [row] = await db
    .select({ push_token: profiles.pushToken })
    .from(profiles)
    .where(eq(profiles.id, userId))
    .limit(1);
  return row?.push_token ?? null;
}

export async function fetchActiveWingpeople(
  db: DBOrTx,
  daterId: string,
): Promise<WingpersonRow[]> {
  const rows = await db
    .select({
      id: contacts.id,
      created_at: contacts.createdAt,
      winger_id: contacts.wingerId,
      winger_chosen_name: profiles.chosenName,
      winger_gender: profiles.gender,
      winger_avatar_url: profiles.avatarUrl,
    })
    .from(contacts)
    .leftJoin(profiles, eq(profiles.id, contacts.wingerId))
    .where(
      and(eq(contacts.userId, daterId), eq(contacts.wingpersonStatus, 'active')),
    )
    .orderBy(asc(contacts.createdAt));
  return rows as WingpersonRow[];
}

export async function fetchIncomingInvitations(
  db: DBOrTx,
  wingerId: string,
): Promise<IncomingInvitationRow[]> {
  const rows = await db
    .select({
      id: contacts.id,
      created_at: contacts.createdAt,
      dater_id: contacts.userId,
      dater_chosen_name: profiles.chosenName,
    })
    .from(contacts)
    .leftJoin(profiles, eq(profiles.id, contacts.userId))
    .where(
      and(eq(contacts.wingerId, wingerId), eq(contacts.wingpersonStatus, 'invited')),
    )
    .orderBy(desc(contacts.createdAt));
  return rows as IncomingInvitationRow[];
}

export async function fetchSentInvitations(
  db: DBOrTx,
  daterId: string,
): Promise<SentInvitationRow[]> {
  const rows = await db
    .select({
      id: contacts.id,
      created_at: contacts.createdAt,
      phone_number: contacts.phoneNumber,
      winger_id: contacts.wingerId,
      winger_chosen_name: profiles.chosenName,
    })
    .from(contacts)
    .leftJoin(profiles, eq(profiles.id, contacts.wingerId))
    .where(
      and(eq(contacts.userId, daterId), eq(contacts.wingpersonStatus, 'invited')),
    )
    .orderBy(desc(contacts.createdAt));
  return rows as SentInvitationRow[];
}

export async function fetchWingingFor(
  db: DBOrTx,
  wingerId: string,
): Promise<WingingForDaterRow[]> {
  const rows = await db
    .select({
      id: contacts.id,
      created_at: contacts.createdAt,
      dater_id: contacts.userId,
      dater_chosen_name: profiles.chosenName,
      dater_avatar_url: profiles.avatarUrl,
      dater_interests: datingProfiles.interests,
      dater_bio: datingProfiles.bio,
      dater_interested_gender: datingProfiles.interestedGender,
    })
    .from(contacts)
    .leftJoin(profiles, eq(profiles.id, contacts.userId))
    .leftJoin(datingProfiles, eq(datingProfiles.userId, contacts.userId))
    .where(
      and(eq(contacts.wingerId, wingerId), eq(contacts.wingpersonStatus, 'active')),
    )
    .orderBy(asc(contacts.createdAt));
  return rows as WingingForDaterRow[];
}

// Counts how many decisions a winger has suggested to a dater in the last 7 days,
// returning a contactId → count map. Single query covers all the dater's
// active wingers at once, so the wingpeople bundle stays O(1) round-trips.
export async function fetchWeeklyCounts(
  db: DBOrTx,
  daterId: string,
  wingpeople: WingpersonRow[],
): Promise<Record<string, number>> {
  const wingerIds: string[] = [];
  const wingerToContactId: Record<string, string> = {};
  for (const w of wingpeople) {
    if (w.winger_id != null) {
      wingerIds.push(w.winger_id);
      wingerToContactId[w.winger_id] = w.id;
    }
  }

  if (wingerIds.length === 0) return {};

  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const rows = await db
    .select({ suggested_by: decisions.suggestedBy })
    .from(decisions)
    .where(
      and(
        eq(decisions.actorId, daterId),
        inArray(decisions.suggestedBy, wingerIds),
        gte(decisions.createdAt, since),
      ),
    );

  const counts: Record<string, number> = {};
  for (const row of rows) {
    if (row.suggested_by == null) continue;
    const contactId = wingerToContactId[row.suggested_by];
    if (contactId) counts[contactId] = (counts[contactId] ?? 0) + 1;
  }
  return counts;
}

export async function findProfileIdByPhone(
  db: DBOrTx,
  phoneNumber: string,
): Promise<string | null> {
  const [row] = await db
    .select({ id: profiles.id })
    .from(profiles)
    .where(eq(profiles.phoneNumber, phoneNumber))
    .limit(1);
  return row?.id ?? null;
}

// Inserts a pending contact for the dater. If a profile already exists with
// that phone number, links winger_id immediately so the auto-link DB trigger
// has nothing to do later.
export async function insertContactInvite(
  db: DBOrTx,
  daterId: string,
  phoneNumber: string,
): Promise<{ id: string; phone_number: string; winger_id: string | null }> {
  const wingerId = await findProfileIdByPhone(db, phoneNumber);
  const [row] = await db
    .insert(contacts)
    .values({
      userId: daterId,
      phoneNumber,
      wingerId,
      wingpersonStatus: 'invited',
    })
    .returning({
      id: contacts.id,
      phone_number: contacts.phoneNumber,
      winger_id: contacts.wingerId,
    });
  return row;
}

// Used by the winger to accept/decline an invitation. Constrained to rows
// where the caller is the winger and the contact is still 'invited' so we
// can't trample a finalized status.
export async function setInvitationStatus(
  db: DBOrTx,
  contactId: string,
  wingerId: string,
  status: 'active' | 'removed',
): Promise<{ updated: boolean }> {
  const rows = await db
    .update(contacts)
    .set({ wingpersonStatus: status })
    .where(
      and(
        eq(contacts.id, contactId),
        eq(contacts.wingerId, wingerId),
        eq(contacts.wingpersonStatus, 'invited'),
      ),
    )
    .returning({ id: contacts.id });
  return { updated: rows.length > 0 };
}

// Used by the dater to remove a wingperson (covers cancel-invite and
// remove-active). Constrained to contacts the dater owns.
export async function removeContactByDater(
  db: DBOrTx,
  contactId: string,
  daterId: string,
): Promise<{ updated: boolean }> {
  const rows = await db
    .update(contacts)
    .set({ wingpersonStatus: 'removed' })
    .where(and(eq(contacts.id, contactId), eq(contacts.userId, daterId)))
    .returning({ id: contacts.id });
  return { updated: rows.length > 0 };
}

