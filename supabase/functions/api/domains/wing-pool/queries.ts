import { and, desc, eq, isNotNull, isNull, ne, notExists, or, sql } from 'drizzle-orm';
import { alias } from 'drizzle-orm/pg-core';
import type { DBOrTx } from '../../db/client.ts';
import { contacts, datingProfiles, decisions, profiles, profilePhotos } from '../../db/schema.ts';
import type { WingPoolRow } from './transformers.ts';

export type FetchWingPoolParams = {
  wingerId: string;
  daterId: string;
  pageSize: number;
  pageOffset: number;
};

export async function isActiveWingperson(
  db: DBOrTx,
  wingerId: string,
  daterId: string,
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

export async function fetchWingPool(
  db: DBOrTx,
  params: FetchWingPoolParams,
): Promise<WingPoolRow[]> {
  const { wingerId, daterId, pageSize, pageOffset } = params;
  const ddp = alias(datingProfiles, 'ddp');

  const ageExpr = sql<number>`extract(year from age(${profiles.dateOfBirth}))::int`;

  const firstPhotoExpr = sql<string | null>`(
    select ${profilePhotos.storageUrl}
    from ${profilePhotos}
    where ${profilePhotos.datingProfileId} = ${datingProfiles.id}
      and ${profilePhotos.approvedAt} is not null
    order by ${profilePhotos.displayOrder}
    limit 1
  )`;

  const filters = [
    eq(datingProfiles.isActive, true),
    eq(datingProfiles.datingStatus, 'open'),
    ne(datingProfiles.userId, daterId),
    ne(datingProfiles.userId, wingerId),
    eq(datingProfiles.city, ddp.city),
    or(
      sql`${ddp.interestedGender} = '{}'::public.gender[]`,
      sql`${profiles.gender} = any(${ddp.interestedGender})`,
    ),
    sql`${ageExpr} >= ${ddp.ageFrom}`,
    or(isNull(ddp.ageTo), sql`${ageExpr} <= ${ddp.ageTo}`),
    or(
      isNull(ddp.religiousPreference),
      sql`${datingProfiles.religion} = ${ddp.religiousPreference}`,
    ),
    notExists(
      db
        .select({ one: sql`1` })
        .from(decisions)
        .where(
          and(
            eq(decisions.actorId, daterId),
            eq(decisions.recipientId, datingProfiles.userId),
            isNotNull(decisions.decision),
          ),
        ),
    ),
  ];

  const rows = await db
    .select({
      profile_id: datingProfiles.id,
      user_id: datingProfiles.userId,
      chosen_name: profiles.chosenName,
      gender: profiles.gender,
      age: ageExpr.as('age'),
      city: datingProfiles.city,
      bio: datingProfiles.bio,
      dating_status: datingProfiles.datingStatus,
      interests: datingProfiles.interests,
      first_photo: firstPhotoExpr.as('first_photo'),
    })
    .from(datingProfiles)
    .innerJoin(profiles, eq(profiles.id, datingProfiles.userId))
    .innerJoin(ddp, eq(ddp.userId, daterId))
    .where(and(...filters))
    .orderBy(desc(datingProfiles.createdAt))
    .limit(pageSize)
    .offset(pageOffset);

  return rows as WingPoolRow[];
}
