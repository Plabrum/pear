import type { DiscoverProfile } from './schemas.ts';

export type DiscoverRow = {
  profile_id: string;
  user_id: string;
  chosen_name: string;
  gender: DiscoverProfile['gender'];
  age: number;
  city: DiscoverProfile['city'];
  bio: string | null;
  dating_status: DiscoverProfile['datingStatus'];
  interests: DiscoverProfile['interests'];
  photos: DiscoverProfile['photos'];
  suggestions: DiscoverProfile['suggestions'];
  prompts: DiscoverProfile['prompts'];
};

export function rowToDiscoverProfile(row: DiscoverRow): DiscoverProfile {
  return {
    profileId: row.profile_id,
    userId: row.user_id,
    chosenName: row.chosen_name,
    gender: row.gender,
    age: row.age,
    city: row.city,
    bio: row.bio,
    datingStatus: row.dating_status,
    interests: row.interests,
    photos: (row.photos ?? []).map((p) => ({ url: p.url, pickedByName: p.pickedByName ?? null })),
    suggestions: row.suggestions ?? [],
    prompts: row.prompts ?? [],
  };
}
