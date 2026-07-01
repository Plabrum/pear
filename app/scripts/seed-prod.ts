#!/usr/bin/env npx tsx
/**
 * Seed 50 fake dater profiles into prod (New York, 25 women + 25 men).
 *
 * Usage:
 *   SUPABASE_URL=https://xxx.supabase.co \
 *   SUPABASE_SERVICE_ROLE_KEY=eyJ... \
 *   npx tsx scripts/seed-prod.ts
 *
 * Idempotent: skips any user whose email already exists.
 * To wipe seed users, delete accounts with email ending in @seed.pear.test.
 */

import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  console.error('Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.');
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { autoRefreshToken: false, persistSession: false },
});

// ── Real users ────────────────────────────────────────────────────────────────

const PHIL_ID = '4c850486-c632-4f10-b328-14b2400edc0e';
const DIANA_ID = '8ec88c34-508b-4872-a8e7-74b07d9d9c7c';

// ── Data ──────────────────────────────────────────────────────────────────────

const WOMEN: { first: string; last: string }[] = [
  { first: 'Emma', last: 'Sullivan' },
  { first: 'Olivia', last: 'Chen' },
  { first: 'Ava', last: 'Rodriguez' },
  { first: 'Sophia', last: 'Kim' },
  { first: 'Isabella', last: 'Patel' },
  { first: 'Mia', last: 'Thompson' },
  { first: 'Charlotte', last: 'Garcia' },
  { first: 'Amelia', last: 'Williams' },
  { first: 'Harper', last: 'Johnson' },
  { first: 'Evelyn', last: 'Davis' },
  { first: 'Luna', last: 'Martinez' },
  { first: 'Scarlett', last: 'Anderson' },
  { first: 'Grace', last: 'Taylor' },
  { first: 'Chloe', last: 'Brown' },
  { first: 'Penelope', last: 'Jackson' },
  { first: 'Layla', last: 'White' },
  { first: 'Riley', last: 'Harris' },
  { first: 'Zoey', last: 'Martin' },
  { first: 'Nora', last: 'Wilson' },
  { first: 'Lily', last: 'Moore' },
  { first: 'Eleanor', last: 'Lee' },
  { first: 'Hannah', last: 'Clark' },
  { first: 'Lillian', last: 'Walker' },
  { first: 'Addison', last: 'Hall' },
  { first: 'Aubrey', last: 'Allen' },
];

const MEN: { first: string; last: string }[] = [
  { first: 'Liam', last: 'Murphy' },
  { first: 'Noah', last: 'Nguyen' },
  { first: 'Oliver', last: 'Sanchez' },
  { first: 'Elijah', last: 'Park' },
  { first: 'James', last: 'Shah' },
  { first: 'Aiden', last: 'Turner' },
  { first: 'Lucas', last: 'Lopez' },
  { first: 'Mason', last: 'Scott' },
  { first: 'Ethan', last: 'Adams' },
  { first: 'Alexander', last: 'Evans' },
  { first: 'Henry', last: 'Rivera' },
  { first: 'Jackson', last: 'Baker' },
  { first: 'Sebastian', last: 'Gonzalez' },
  { first: 'Jack', last: 'Nelson' },
  { first: 'Owen', last: 'Carter' },
  { first: 'Theodore', last: 'Mitchell' },
  { first: 'Caleb', last: 'Perez' },
  { first: 'Luke', last: 'Roberts' },
  { first: 'Gabriel', last: 'Torres' },
  { first: 'Isaac', last: 'Phillips' },
  { first: 'Anthony', last: 'Campbell' },
  { first: 'Dylan', last: 'Parker' },
  { first: 'Carter', last: 'Collins' },
  { first: 'Wyatt', last: 'Edwards' },
  { first: 'Julian', last: 'Stewart' },
];

const RELIGIONS = [
  'Christian',
  'Jewish',
  'Muslim',
  'Hindu',
  'Buddhist',
  'Agnostic',
  'Atheist',
  'Other',
  'Prefer not to say',
] as const;

const ALL_INTERESTS = [
  'Travel',
  'Fitness',
  'Cooking',
  'Music',
  'Art',
  'Movies',
  'Books',
  'Gaming',
  'Outdoors',
  'Sports',
  'Technology',
  'Fashion',
  'Food',
  'Photography',
  'Dance',
  'Volunteering',
] as const;

const BIOS = [
  'Brooklyn native, always hunting for the best bagel in the borough.',
  'Financial district by day, aspiring chef by night. Will judge your restaurant choices.',
  'Love a good rooftop at golden hour. Looking for someone to share the view with.',
  'Museum hopper and amateur pottery enthusiast. My hands are always a little dusty.',
  'Ran the NYC Marathon once. Now I only run for the brunch at the finish line.',
  'I once got lost in Central Park on purpose. 10/10 would recommend.',
  'Amateur stand-up comic. My friends laugh at me, not with me — close enough.',
  'Reading on the subway is my meditation. Currently into a fantasy novel the size of a brick.',
  'Weekend farmers market devotee. I own too many varieties of hot sauce.',
  'Dog parent to a golden retriever named Pretzel who runs my apartment.',
  'Used to claim I hate musicals. Bought Broadway season tickets six months later.',
  'Jazz bars and dive bars. Ideally the same bar on the same night.',
  'Spent six months living out of a backpack. Now I live in Astoria. Progress.',
  'Part-time yoga instructor, full-time overthinker. Working on the balance.',
  'The person who reads the menu top to bottom before ordering. Worth it every time.',
  'True crime podcast listener who is, paradoxically, very optimistic about people.',
  'I will beat you at trivia night and then apologize about it.',
  "Architecture nerd. I will stop mid-walk to stare at a building and I'm not sorry.",
  "Moved here for grad school and stayed for the energy. Five years in, still can't explain it.",
  'My ideal Saturday: bike ride along the Hudson, good coffee, no plans after noon.',
  'Gallery hopper every first Friday. Looking for someone to argue about contemporary art with.',
  'Home cook who takes the farmers market way too seriously.',
  'Fluent in three languages and sarcasm. The sarcasm sees the most use.',
  'I make really good playlists. This is not a small thing.',
  'Ask me about the best ramen spot in the city. I have opinions.',
];

const PROMPT_QUESTIONS = [
  'The way to my heart is…',
  'A perfect Sunday looks like…',
  'My love language is…',
  'I get way too excited about…',
  "The most spontaneous thing I've done…",
  'Two truths and a lie…',
  'My friends would describe me as…',
  "I'm looking for someone who…",
  'Unpopular opinion I hold…',
  'My go-to karaoke song…',
];

const PROMPT_ANSWERS: Record<string, string[]> = {
  'The way to my heart is…': [
    'a well-timed restaurant rec and a willingness to share appetizers.',
    'remembering the random thing I mentioned once in passing.',
    "showing up with snacks I didn't ask for.",
  ],
  'A perfect Sunday looks like…': [
    'farmers market, long brunch, zero alarms.',
    'coffee, crossword, a walk with no destination.',
    'cooking something complicated and not rushing it.',
  ],
  'My love language is…': [
    "acts of service. I'll fix your IKEA furniture without being asked.",
    'quality time — the kind where we can also just sit quietly.',
    'words of affirmation, which I find embarrassing to admit.',
  ],
  'I get way too excited about…': [
    'when a new bakery opens in the neighborhood.',
    'finding a great parking spot. Never take that for granted.',
    'obscure historical facts that nobody asked for.',
  ],
  "The most spontaneous thing I've done…": [
    'booked a flight to Lisbon 48 hours before departure. No regrets.',
    'quit a stable job to go work on a farm for three months.',
    'said yes to a last-minute road trip and was gone for two weeks.',
  ],
  'Two truths and a lie…': [
    "I've been to 30 countries. I can juggle. I once met Paul McCartney. Figure it out.",
    "I have a twin. I've run a half marathon. I don't drink coffee. One is false.",
    "I grew up on a farm. I speak Mandarin. I've been skydiving. Your guess.",
  ],
  'My friends would describe me as…': [
    'the one who actually makes a reservation.',
    'reliably late but worth waiting for.',
    'the person who asks the questions everyone was thinking.',
  ],
  "I'm looking for someone who…": [
    'takes brunch as seriously as I do.',
    "is curious about the world and doesn't pretend to have it figured out.",
    'can disagree with me and still be kind about it.',
  ],
  'Unpopular opinion I hold…': [
    'pizza is better the next day. Not sorry.',
    'the 6 train is actually fine.',
    'a picnic beats any restaurant if the weather cooperates.',
  ],
  'My go-to karaoke song…': [
    '"Mr. Brightside" — no hesitation, no shame.',
    '"Total Eclipse of the Heart" and I fully commit.',
    'Something 90s that I know every single word to.',
  ],
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pickN<T>(arr: readonly T[], n: number): T[] {
  return [...arr].sort(() => Math.random() - 0.5).slice(0, n);
}

function randomDob(minAge: number, maxAge: number): string {
  const now = new Date();
  const year = now.getFullYear() - minAge - Math.floor(Math.random() * (maxAge - minAge + 1));
  const month = String(Math.floor(Math.random() * 12) + 1).padStart(2, '0');
  const day = String(Math.floor(Math.random() * 28) + 1).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// ── Seed logic ────────────────────────────────────────────────────────────────

async function ensurePromptTemplates(): Promise<void> {
  const { data } = await supabase.from('prompt_templates').select('id').limit(1);
  if (data && data.length > 0) {
    console.log('  prompt_templates already populated, skipping');
    return;
  }
  const { error } = await supabase
    .from('prompt_templates')
    .insert(PROMPT_QUESTIONS.map((question) => ({ question })));
  if (error) throw error;
  console.log(`  inserted ${PROMPT_QUESTIONS.length} prompt templates`);
}

async function seedPerson(
  index: number,
  first: string,
  last: string,
  gender: 'Male' | 'Female',
  photoIndex: number
): Promise<void> {
  const email = `seed.${first.toLowerCase()}.${last.toLowerCase()}@seed.pear.test`;
  const label = `[${String(index + 1).padStart(2, ' ')}/50] ${first} ${last}`;

  // 1. Create auth user
  const { data: authData, error: authError } = await supabase.auth.admin.createUser({
    email,
    password: 'Pear123!',
    email_confirm: true,
    user_metadata: { full_name: `${first} ${last}` },
  });

  if (authError) {
    if (
      authError.message.toLowerCase().includes('already been registered') ||
      authError.message.toLowerCase().includes('already exists')
    ) {
      console.log(`  ${label} — already exists, skipping`);
      return;
    }
    throw new Error(`${label} auth error: ${authError.message}`);
  }

  const userId = authData.user.id;

  // 2. Update the profile row created by the DB trigger
  const { error: profileError } = await supabase
    .from('profiles')
    .update({
      chosen_name: first,
      last_name: last,
      date_of_birth: randomDob(22, 35),
      gender,
      role: 'dater',
      // Fake but unique US phone numbers
      phone_number: `+1555${String(1000000 + index * 7919).slice(0, 7)}`,
    })
    .eq('id', userId);

  if (profileError) throw new Error(`${label} profile error: ${profileError.message}`);

  // 3. Create dating_profile
  const { data: dp, error: dpError } = await supabase
    .from('dating_profiles')
    .insert({
      user_id: userId,
      bio: pick(BIOS),
      interested_gender: gender === 'Female' ? ['Male'] : ['Female'],
      age_from: 22,
      age_to: 38,
      religion: pick(RELIGIONS),
      interests: pickN(ALL_INTERESTS, 3 + Math.floor(Math.random() * 3)),
      city: 'New York',
      is_active: true,
      dating_status: 'open',
    })
    .select('id')
    .single();

  if (dpError) throw new Error(`${label} dating_profile error: ${dpError.message}`);

  // 4. Add 3 prompt answers
  const { data: templates } = await supabase.from('prompt_templates').select('id, question');
  if (templates && templates.length > 0) {
    const picked = pickN(templates, 3);
    const { error: promptError } = await supabase.from('profile_prompts').insert(
      picked.map((t) => ({
        dating_profile_id: dp.id,
        prompt_template_id: t.id,
        answer: pick(PROMPT_ANSWERS[t.question] ?? ['Something interesting about me.']),
      }))
    );
    if (promptError) throw new Error(`${label} prompts error: ${promptError.message}`);
  }

  // 5. Add 2 photos (randomuser.me portraits are deterministic by index)
  const genderPath = gender === 'Female' ? 'women' : 'men';
  const { error: photoError } = await supabase.from('profile_photos').insert([
    {
      dating_profile_id: dp.id,
      storage_url: `https://randomuser.me/api/portraits/${genderPath}/${photoIndex % 99}.jpg`,
      display_order: 0,
      approved_at: new Date().toISOString(),
    },
    {
      dating_profile_id: dp.id,
      storage_url: `https://randomuser.me/api/portraits/${genderPath}/${(photoIndex + 25) % 99}.jpg`,
      display_order: 1,
      approved_at: new Date().toISOString(),
    },
  ]);
  if (photoError) throw new Error(`${label} photos error: ${photoError.message}`);

  console.log(`  ${label} ✓`);
}

// Have all seed users of the given gender like a real user.
// Idempotent — uses upsert with ignoreDuplicates so re-runs are safe.
async function seedDecisions(targetId: string, gender: 'Male' | 'Female'): Promise<void> {
  const nameList = gender === 'Female' ? WOMEN : MEN;
  const seedEmails = new Set(
    nameList.map((p) => `seed.${p.first.toLowerCase()}.${p.last.toLowerCase()}@seed.pear.test`)
  );

  const { data, error } = await supabase.auth.admin.listUsers({ perPage: 1000 });
  if (error) throw new Error(`listUsers error: ${error.message}`);

  const actorIds = data.users.filter((u) => u.email && seedEmails.has(u.email)).map((u) => u.id);

  if (actorIds.length === 0) {
    console.log(`  no ${gender} seed users found — run the seed first`);
    return;
  }

  const rows = actorIds.map((actor_id) => ({
    actor_id,
    recipient_id: targetId,
    decision: 'approved' as const,
  }));

  const { error: decisionError } = await supabase
    .from('decisions')
    .upsert(rows, { onConflict: 'actor_id,recipient_id', ignoreDuplicates: true });

  if (decisionError) throw new Error(`decisions error: ${decisionError.message}`);
  console.log(`  ${actorIds.length} ${gender} seed users → liked ${targetId}`);
}

async function main(): Promise<void> {
  console.log('Seeding 50 dater profiles in New York…\n');

  await ensurePromptTemplates();
  console.log();

  const people = [
    ...WOMEN.map((p, i) => ({ ...p, gender: 'Female' as const, photoIndex: i })),
    ...MEN.map((p, i) => ({ ...p, gender: 'Male' as const, photoIndex: i })),
  ];

  for (let i = 0; i < people.length; i++) {
    const { first, last, gender, photoIndex } = people[i];
    await seedPerson(i, first, last, gender, photoIndex);
  }

  console.log('\nSeeding decisions (likes → real users)…');
  await seedDecisions(PHIL_ID, 'Female'); // 25 women like Phil
  await seedDecisions(DIANA_ID, 'Male'); // 25 men like Diana

  console.log('\nDone. All 50 profiles are live in New York.');
}

main().catch((err) => {
  console.error('\nSeed failed:', err);
  process.exit(1);
});
