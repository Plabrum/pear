import type {
  IncomingInvitation,
  SentInvitation,
  WingingForRow,
  Wingperson,
} from './schemas.ts';

type GenderValue = NonNullable<Wingperson['winger']>['gender'];
type InterestList = NonNullable<WingingForRow['dater']>['interests'];
type GenderList = NonNullable<WingingForRow['dater']>['interestedGender'];

export type WingpersonRow = {
  id: string;
  created_at: string;
  winger_id: string | null;
  winger_chosen_name: string | null;
  winger_gender: GenderValue;
  winger_avatar_url: string | null;
};

export type IncomingInvitationRow = {
  id: string;
  created_at: string;
  dater_id: string | null;
  dater_chosen_name: string | null;
};

export type WingingForDaterRow = {
  id: string;
  created_at: string;
  dater_id: string | null;
  dater_chosen_name: string | null;
  dater_avatar_url: string | null;
  dater_interests: InterestList;
  dater_bio: string | null;
  dater_interested_gender: GenderList;
};

export type SentInvitationRow = {
  id: string;
  created_at: string;
  phone_number: string;
  winger_id: string | null;
  winger_chosen_name: string | null;
};

export function rowToWingperson(row: WingpersonRow): Wingperson {
  return {
    id: row.id,
    createdAt: row.created_at,
    winger:
      row.winger_id != null
        ? {
            id: row.winger_id,
            chosenName: row.winger_chosen_name,
            gender: row.winger_gender,
            avatarUrl: row.winger_avatar_url,
          }
        : null,
  };
}

export function rowToIncomingInvitation(row: IncomingInvitationRow): IncomingInvitation {
  return {
    id: row.id,
    createdAt: row.created_at,
    dater:
      row.dater_id != null
        ? { id: row.dater_id, chosenName: row.dater_chosen_name }
        : null,
  };
}

export function rowToWingingFor(row: WingingForDaterRow): WingingForRow {
  return {
    id: row.id,
    createdAt: row.created_at,
    dater:
      row.dater_id != null
        ? {
            id: row.dater_id,
            chosenName: row.dater_chosen_name,
            avatarUrl: row.dater_avatar_url,
            interests: row.dater_interests,
            bio: row.dater_bio,
            interestedGender: row.dater_interested_gender,
          }
        : null,
  };
}

export function rowToSentInvitation(row: SentInvitationRow): SentInvitation {
  return {
    id: row.id,
    createdAt: row.created_at,
    phoneNumber: row.phone_number,
    winger:
      row.winger_id != null
        ? { id: row.winger_id, chosenName: row.winger_chosen_name }
        : null,
  };
}
