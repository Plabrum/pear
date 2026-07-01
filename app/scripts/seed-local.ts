#!/usr/bin/env npx tsx
/**
 * Seed local dev database with a dev user + 50 fake dater profiles.
 *
 * Usage (via npm run db:fixtures — sets env vars automatically):
 *   SUPABASE_URL=http://127.0.0.1:54321 \
 *   SUPABASE_SERVICE_ROLE_KEY=<local-service-role-key> \
 *   npx tsx scripts/seed-local.ts
 *
 * Idempotent: skips any user whose email already exists.
 */

import { createClient } from '@supabase/supabase-js';
import { createPrivateKey } from 'crypto';
import jwt from 'jsonwebtoken';

const SUPABASE_URL = process.env.SUPABASE_URL ?? 'http://127.0.0.1:54321';
const GOTRUE_JWT_KEYS = process.env.GOTRUE_JWT_KEYS;
const GOTRUE_JWT_SECRET = process.env.GOTRUE_JWT_SECRET;

function makeServiceRoleJwt(): string {
  const claims = {
    iss: 'supabase-demo',
    role: 'service_role',
    exp: Math.floor(Date.now() / 1000) + 3600,
  };

  if (GOTRUE_JWT_KEYS) {
    // Asymmetric ES256 keys (newer Supabase CLI)
    const jwks: (JsonWebKey & { kid?: string })[] = JSON.parse(GOTRUE_JWT_KEYS);
    const jwk = jwks.find((k) => k.d); // find a private key
    if (!jwk) throw new Error('No private key found in GOTRUE_JWT_KEYS');
    const privateKey = createPrivateKey({ format: 'jwk', key: jwk });
    return jwt.sign(claims, privateKey, { algorithm: 'ES256', keyid: jwk.kid });
  }

  if (GOTRUE_JWT_SECRET) {
    return jwt.sign(claims, GOTRUE_JWT_SECRET, { algorithm: 'HS256' });
  }

  throw new Error('Neither GOTRUE_JWT_KEYS nor GOTRUE_JWT_SECRET is set.');
}

const serviceRoleJwt = makeServiceRoleJwt();

const supabase = createClient(SUPABASE_URL, serviceRoleJwt, {
  auth: { autoRefreshToken: false, persistSession: false },
});

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

async function ensureDevUser(): Promise<string> {
  const DEV_EMAIL = 'dev@local.test';

  // Check if user already exists
  const { data: listData, error: listError } = await supabase.auth.admin.listUsers({
    perPage: 1000,
  });
  if (listError) throw new Error(`listUsers error: ${listError.message}`);

  const existing = listData.users.find((u) => u.email === DEV_EMAIL);
  if (existing) {
    console.log(`  dev user already exists (${existing.id}), skipping creation`);
    return existing.id;
  }

  const { data: authData, error: authError } = await supabase.auth.admin.createUser({
    email: DEV_EMAIL,
    password: 'devpassword',
    email_confirm: true,
  });
  if (authError) throw new Error(`dev user auth error: ${authError.message}`);

  const userId = authData.user.id;

  const { error: profileError } = await supabase
    .from('profiles')
    .update({
      chosen_name: 'Dev',
      last_name: 'User',
      gender: 'Male',
      date_of_birth: '1993-01-01',
      role: 'dater',
      phone_number: '+15550000000',
    })
    .eq('id', userId);
  if (profileError) throw new Error(`dev user profile error: ${profileError.message}`);

  const { error: dpError } = await supabase.from('dating_profiles').insert({
    user_id: userId,
    bio: 'Local dev user. Here to test the app.',
    interested_gender: ['Female', 'Male'],
    age_from: 22,
    age_to: 40,
    religion: 'Agnostic',
    interests: ['Travel', 'Technology', 'Food'],
    city: 'New York',
    is_active: true,
    dating_status: 'open',
  });
  if (dpError) throw new Error(`dev user dating_profile error: ${dpError.message}`);

  // Add 3 prompts
  const { data: templates } = await supabase.from('prompt_templates').select('id, question');
  if (templates && templates.length > 0) {
    const picked = pickN(templates, 3);
    const { data: dp } = await supabase
      .from('dating_profiles')
      .select('id')
      .eq('user_id', userId)
      .single();
    if (dp) {
      await supabase.from('profile_prompts').insert(
        picked.map((t) => ({
          dating_profile_id: dp.id,
          prompt_template_id: t.id,
          answer: pick(PROMPT_ANSWERS[t.question] ?? ['Something interesting about me.']),
        }))
      );
    }
  }

  console.log(`  dev user created (${userId})`);
  return userId;
}

async function seedPerson(
  index: number,
  first: string,
  last: string,
  gender: 'Male' | 'Female',
  photoIndex: number
): Promise<void> {
  const email = `seed.${first.toLowerCase()}.${last.toLowerCase()}@seed.pear.test`;
  const label = `[${String(index + 1).padStart(2, '0')}/50] ${first} ${last}`;

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

// Have all seed users of the given gender like the dev user.
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
  console.log(`  ${actorIds.length} ${gender} seed users → liked dev user`);
}

// ── Wingpeople seed ───────────────────────────────────────────────────────────

// Three sample wingpeople who are actively winging for the dev user.
// Order matters — seedWingerPromptResponses assumes [Alex, Jordan, Sam Rivera].
const SAMPLE_WINGERS = [
  { first: 'Alex', last: 'Chen', gender: 'Male' as const, phone: '+15550010001' },
  { first: 'Jordan', last: 'Kim', gender: 'Female' as const, phone: '+15550010002' },
  { first: 'Sam', last: 'Rivera', gender: 'Male' as const, phone: '+15550010003' },
];

// Two seed daters (by email) that the dev user will wing for.
const WINGING_FOR_EMAILS = ['seed.emma.sullivan@seed.pear.test', 'seed.liam.murphy@seed.pear.test'];

async function ensureWingerProfile(
  first: string,
  last: string,
  gender: 'Male' | 'Female',
  phone: string
): Promise<string> {
  const email = `winger.${first.toLowerCase()}.${last.toLowerCase()}@seed.pear.test`;

  const { data: listData } = await supabase.auth.admin.listUsers({ perPage: 1000 });
  const existing = listData?.users.find((u) => u.email === email);
  if (existing) {
    console.log(`  winger ${first} ${last} already exists, skipping`);
    return existing.id;
  }

  const { data: authData, error: authError } = await supabase.auth.admin.createUser({
    email,
    password: 'Pear123!',
    email_confirm: true,
  });
  if (authError) throw new Error(`winger ${first} auth error: ${authError.message}`);

  const userId = authData.user.id;

  const { error: profileError } = await supabase
    .from('profiles')
    .update({
      chosen_name: first,
      last_name: last,
      gender,
      date_of_birth: randomDob(22, 35),
      role: 'winger',
      phone_number: phone,
    })
    .eq('id', userId);
  if (profileError) throw new Error(`winger ${first} profile error: ${profileError.message}`);

  console.log(`  winger ${first} ${last} created (${userId})`);
  return userId;
}

async function seedWingpeopleContacts(devUserId: string): Promise<string[]> {
  const wingerIds: string[] = [];

  // 1. Create winger profiles and link them as active wingpeople of the dev user.
  for (const w of SAMPLE_WINGERS) {
    const wingerId = await ensureWingerProfile(w.first, w.last, w.gender, w.phone);
    wingerIds.push(wingerId);

    const { data: existing } = await supabase
      .from('contacts')
      .select('id')
      .eq('user_id', devUserId)
      .eq('winger_id', wingerId)
      .maybeSingle();

    if (!existing) {
      const { error } = await supabase.from('contacts').insert({
        user_id: devUserId,
        winger_id: wingerId,
        phone_number: w.phone,
        wingperson_status: 'active',
      });
      if (error) throw new Error(`contact for winger ${w.first} error: ${error.message}`);
    }
  }

  // 2. Find the two seed daters and create contacts with dev user as their winger.
  const { data: listData } = await supabase.auth.admin.listUsers({ perPage: 1000 });
  for (const email of WINGING_FOR_EMAILS) {
    const dater = listData?.users.find((u) => u.email === email);
    if (!dater) {
      console.log(`  dater ${email} not found — skipping`);
      continue;
    }

    const { data: daterProfile } = await supabase
      .from('profiles')
      .select('phone_number')
      .eq('id', dater.id)
      .single();

    const phone = daterProfile?.phone_number ?? `+1555999${WINGING_FOR_EMAILS.indexOf(email)}`;

    const { data: existing } = await supabase
      .from('contacts')
      .select('id')
      .eq('user_id', dater.id)
      .eq('winger_id', devUserId)
      .maybeSingle();

    if (!existing) {
      const { error } = await supabase.from('contacts').insert({
        user_id: dater.id,
        winger_id: devUserId,
        phone_number: phone,
        wingperson_status: 'active',
      });
      if (error) throw new Error(`contact winging-for ${email} error: ${error.message}`);
    }

    console.log(`  dev user is now winging for ${email}`);
  }

  return wingerIds;
}

// ── Sam Taylor scenario ───────────────────────────────────────────────────────

const SAM_PROMPTS: { question: string; answer: string }[] = [
  {
    question: 'A perfect Sunday looks like…',
    answer:
      'a slow morning run along the Hudson, eggs somewhere with too-good coffee, then zero plans.',
  },
  {
    question: "I'm looking for someone who…",
    answer: "is curious about the world and doesn't pretend to have it all figured out.",
  },
  {
    question: 'My friends would describe me as…',
    answer: 'the one who actually makes a reservation — and then talks everyone into a detour.',
  },
];

const SAM_MATCHES: {
  first: string;
  last: string;
  bio: string;
  interests: string[];
  religion: string;
  photoIndex: number;
}[] = [
  {
    first: 'Marcus',
    last: 'Webb',
    bio: 'Architecture nerd who will stop mid-walk to stare at a building. Zero apologies.',
    interests: ['Art', 'Travel', 'Food'],
    religion: 'Agnostic',
    photoIndex: 10,
  },
  {
    first: 'Daniel',
    last: 'Okafor',
    bio: 'Jazz bars and dive bars — ideally the same bar on the same night.',
    interests: ['Music', 'Food', 'Outdoors'],
    religion: 'Christian',
    photoIndex: 15,
  },
  {
    first: 'Tyler',
    last: 'Brennan',
    bio: 'I make really good playlists. This is not a small thing.',
    interests: ['Music', 'Movies', 'Gaming'],
    religion: 'Atheist',
    photoIndex: 20,
  },
  {
    first: 'Raj',
    last: 'Iyer',
    bio: 'Home cook who takes the farmers market too seriously. Farmer-market receipts available on request.',
    interests: ['Cooking', 'Travel', 'Books'],
    religion: 'Hindu',
    photoIndex: 25,
  },
  {
    first: 'Cole',
    last: 'Nakamura',
    bio: 'Will beat you at trivia night and apologize about it the whole way home.',
    interests: ['Books', 'Technology', 'Fitness'],
    religion: 'Agnostic',
    photoIndex: 30,
  },
  {
    first: 'Leo',
    last: 'Ferreira',
    bio: 'Ran the NYC Marathon once. Now I only run for the brunch at the finish line.',
    interests: ['Fitness', 'Food', 'Travel'],
    religion: 'Other',
    photoIndex: 35,
  },
  {
    first: 'Finn',
    last: "O'Sullivan",
    bio: 'True crime podcast listener who is, paradoxically, very optimistic about people.',
    interests: ['Books', 'Movies', 'Outdoors'],
    religion: 'Atheist',
    photoIndex: 40,
  },
  {
    first: 'Andre',
    last: 'Moreau',
    bio: 'Moved here from Montreal. The bagels are different but the energy is worth it.',
    interests: ['Food', 'Art', 'Dance'],
    religion: 'Agnostic',
    photoIndex: 45,
  },
  {
    first: 'Kai',
    last: 'Hoffman',
    bio: 'My ideal Saturday: bike ride along the Hudson, good coffee, no plans after noon.',
    interests: ['Outdoors', 'Photography', 'Fitness'],
    religion: 'Atheist',
    photoIndex: 50,
  },
  {
    first: 'Miles',
    last: 'Ashford',
    bio: 'Amateur stand-up comic. My friends laugh at me, not with me — close enough.',
    interests: ['Movies', 'Music', 'Food'],
    religion: 'Jewish',
    photoIndex: 55,
  },
];

async function getOrCreateUser(
  email: string,
  label: string
): Promise<{ id: string; existed: boolean }> {
  const { data: listData, error } = await supabase.auth.admin.listUsers({ perPage: 1000 });
  if (error) throw new Error(`listUsers: ${error.message}`);

  const existing = listData.users.find((u) => u.email === email);
  if (existing) return { id: existing.id, existed: true };

  const { data: authData, error: authError } = await supabase.auth.admin.createUser({
    email,
    password: 'Pear123!',
    email_confirm: true,
  });
  if (authError) throw new Error(`${label} auth error: ${authError.message}`);
  return { id: authData.user.id, existed: false };
}

async function ensureSamTaylor(): Promise<string> {
  const email = 'sam.taylor@seed.pear.test';
  const { id: userId, existed } = await getOrCreateUser(email, 'Sam Taylor');

  if (existed) {
    console.log('  Sam Taylor already exists, skipping creation');
    return userId;
  }

  const { error: profileError } = await supabase
    .from('profiles')
    .update({
      chosen_name: 'Sam',
      last_name: 'Taylor',
      gender: 'Female',
      date_of_birth: randomDob(25, 30),
      role: 'dater',
      phone_number: '+15550020001',
    })
    .eq('id', userId);
  if (profileError) throw new Error(`Sam profile error: ${profileError.message}`);

  const { data: dp, error: dpError } = await supabase
    .from('dating_profiles')
    .insert({
      user_id: userId,
      bio: 'Brooklyn native, always hunting for the best bagel in the borough. Big on live music and even bigger on people who can keep up with a 9pm whim.',
      interested_gender: ['Male'],
      age_from: 25,
      age_to: 38,
      religion: 'Agnostic',
      interests: ['Music', 'Outdoors', 'Food', 'Travel', 'Art'],
      city: 'New York',
      is_active: true,
      dating_status: 'winging',
    })
    .select('id')
    .single();
  if (dpError) throw new Error(`Sam dating_profile error: ${dpError.message}`);

  const { data: templates } = await supabase.from('prompt_templates').select('id, question');
  if (templates) {
    const rows = SAM_PROMPTS.flatMap(({ question, answer }) => {
      const template = templates.find((t) => t.question === question);
      if (!template) {
        console.warn(`  prompt template not found: "${question}" — skipping`);
        return [];
      }
      return [{ dating_profile_id: dp.id, prompt_template_id: template.id, answer }];
    });
    if (rows.length > 0) {
      const { error: promptError } = await supabase.from('profile_prompts').insert(rows);
      if (promptError) throw new Error(`Sam prompts error: ${promptError.message}`);
    }
  }

  const { error: photoError } = await supabase.from('profile_photos').insert({
    dating_profile_id: dp.id,
    storage_url: `https://randomuser.me/api/portraits/women/5.jpg`,
    display_order: 0,
    approved_at: new Date().toISOString(),
  });
  if (photoError) throw new Error(`Sam photo error: ${photoError.message}`);

  console.log(`  Sam Taylor created (${userId})`);
  return userId;
}

async function ensureSamMatch(index: number, m: (typeof SAM_MATCHES)[number]): Promise<void> {
  const email = `sam.match.${m.first.toLowerCase()}.${m.last.toLowerCase()}@seed.pear.test`;
  const label = `${m.first} ${m.last}`;
  const { id: userId, existed } = await getOrCreateUser(email, label);

  if (existed) {
    console.log(`  ${label} already exists, skipping`);
    return;
  }

  const { error: profileError } = await supabase
    .from('profiles')
    .update({
      chosen_name: m.first,
      last_name: m.last,
      date_of_birth: randomDob(25, 35),
      gender: 'Male',
      role: 'dater',
      phone_number: `+1555002${String(index + 10).padStart(4, '0')}`,
    })
    .eq('id', userId);
  if (profileError) throw new Error(`${label} profile error: ${profileError.message}`);

  const { data: dp, error: dpError } = await supabase
    .from('dating_profiles')
    .insert({
      user_id: userId,
      bio: m.bio,
      interested_gender: ['Female'],
      age_from: 23,
      age_to: 38,
      religion: m.religion,
      interests: m.interests,
      city: 'New York',
      is_active: true,
      dating_status: 'open',
    })
    .select('id')
    .single();
  if (dpError) throw new Error(`${label} dating_profile error: ${dpError.message}`);

  const { error: photoError } = await supabase.from('profile_photos').insert([
    {
      dating_profile_id: dp.id,
      storage_url: `https://randomuser.me/api/portraits/men/${m.photoIndex % 99}.jpg`,
      display_order: 0,
      approved_at: new Date().toISOString(),
    },
    {
      dating_profile_id: dp.id,
      storage_url: `https://randomuser.me/api/portraits/men/${(m.photoIndex + 20) % 99}.jpg`,
      display_order: 1,
      approved_at: new Date().toISOString(),
    },
  ]);
  if (photoError) throw new Error(`${label} photos error: ${photoError.message}`);

  console.log(`  ${label} ✓`);
}

async function seedSamScenario(devUserId: string): Promise<void> {
  const samId = await ensureSamTaylor();

  for (let i = 0; i < SAM_MATCHES.length; i++) {
    await ensureSamMatch(i, SAM_MATCHES[i]);
  }

  const { data: existing } = await supabase
    .from('contacts')
    .select('id')
    .eq('user_id', samId)
    .eq('winger_id', devUserId)
    .maybeSingle();

  if (existing) {
    console.log("  dev user already linked as Sam's winger, skipping");
    return;
  }

  const { error } = await supabase.from('contacts').insert({
    user_id: samId,
    winger_id: devUserId,
    phone_number: '+15550020001',
    wingperson_status: 'active',
  });
  if (error) throw new Error(`Sam contact error: ${error.message}`);
  console.log(`  dev user linked as Sam's winger ✓`);
}

// ── Winger prompt responses ───────────────────────────────────────────────────

// Each question maps to one response per winger: [Alex, Jordan, Sam Rivera]
const RESPONSES_BY_QUESTION: Record<string, [string, string, string]> = {
  'The way to my heart is…': [
    'Can confirm — bring snacks and you have their full attention.',
    'This is 100% accurate. I have tested this theory.',
    "Honestly though, they mean it. Don't show up empty-handed.",
  ],
  'A perfect Sunday looks like…': [
    "They will genuinely not check their phone until 2pm. It's impressive.",
    'The farmers market thing is real. They know every vendor by name.',
    'Add "convincing everyone else to cancel their plans too" and this is perfect.',
  ],
  'My love language is…': [
    "I once watched them rearrange someone else's furniture unprompted. True story.",
    'They say quality time but they also just show up with your favorite snacks. Both.',
    'The quiet sitting together thing sounds boring until you experience it. It is not boring.',
  ],
  'I get way too excited about…': [
    'You think they are joking about this. They are not joking.',
    'I have received approximately 14 texts about new bakery openings in the last month.',
    'The parking spot thing — I was there. Celebration lasted longer than finding it.',
  ],
  "The most spontaneous thing I've done…": [
    'I heard about this trip 36 hours before departure. Zero hesitation.',
    'They did not pack enough socks. They do not regret a single thing.',
    'This is the most on-brand story I have ever heard about this person.',
  ],
  'Two truths and a lie…': [
    'I know which one is the lie and I am not telling you.',
    'Asked them and they refused to confirm. Part of the charm.',
    'I guessed wrong. Very embarrassing. Do better than me.',
  ],
  'My friends would describe me as…': [
    'Can confirm. They made the reservation for my birthday before I even mentioned it.',
    'The questions thing is real. Best conversation starter I know.',
    'Reliably late is generous. Worth the wait is accurate.',
  ],
  "I'm looking for someone who…": [
    'They will know within five minutes whether you meet this standard.',
    'The brunch thing is non-negotiable. I have seen people fail this test.',
    'Curious and kind. Simple bar. Somehow rare.',
  ],
  'Unpopular opinion I hold…': [
    'I have seen them eat cold pizza for breakfast with zero shame. Committed.',
    'They sent me a voice note about this at 11pm. It was persuasive.',
    'Wrong about the 6 train, right about everything else.',
  ],
  'My go-to karaoke song…': [
    'I have witnessed this. It is a full performance. Respect.',
    'They know every word. Every. Single. Word. Do not underestimate.',
    'Nobody in the room is ready when this song comes on.',
  ],
};

const FALLBACK_RESPONSES: [string, string, string] = [
  'I can personally vouch for this. No notes.',
  "This is the most accurate thing they've ever written about themselves.",
  'Knew them for years and this tracks completely.',
];

async function seedWingerPromptResponses(devUserId: string, wingerIds: string[]): Promise<void> {
  if (wingerIds.length !== 3) {
    throw new Error(`Expected 3 winger IDs, got ${wingerIds.length}`);
  }

  const { data: dp, error: dpError } = await supabase
    .from('dating_profiles')
    .select(`id, prompts:profile_prompts(id, template:prompt_templates(question))`)
    .eq('user_id', devUserId)
    .single();
  if (dpError) throw dpError;
  if (!dp.prompts || dp.prompts.length === 0) {
    console.log('  dev user has no prompts, skipping');
    return;
  }

  let inserted = 0;
  let skipped = 0;

  for (const prompt of dp.prompts) {
    const question = (prompt.template as { question?: string } | null)?.question ?? '';
    const responses = RESPONSES_BY_QUESTION[question] ?? FALLBACK_RESPONSES;

    for (let i = 0; i < wingerIds.length; i++) {
      const wingerId = wingerIds[i];
      const message = responses[i];

      const { data: existing } = await supabase
        .from('prompt_responses')
        .select('id')
        .eq('user_id', wingerId)
        .eq('profile_prompt_id', prompt.id)
        .maybeSingle();

      if (existing) {
        skipped++;
        continue;
      }

      const { error } = await supabase.from('prompt_responses').insert({
        user_id: wingerId,
        profile_prompt_id: prompt.id,
        message,
        is_approved: false,
      });
      if (error) throw new Error(`prompt response insert error: ${error.message}`);
      inserted++;
    }
  }

  console.log(`  ${inserted} winger responses inserted, ${skipped} skipped`);
}

async function main(): Promise<void> {
  console.log('Setting up local dev database…\n');

  await ensurePromptTemplates();
  console.log();

  console.log('Creating dev user (dev@local.test)…');
  const devUserId = await ensureDevUser();
  console.log();

  console.log('Seeding 50 dater profiles in New York…\n');

  const people = [
    ...WOMEN.map((p, i) => ({ ...p, gender: 'Female' as const, photoIndex: i })),
    ...MEN.map((p, i) => ({ ...p, gender: 'Male' as const, photoIndex: i })),
  ];

  for (let i = 0; i < people.length; i++) {
    const { first, last, gender, photoIndex } = people[i];
    await seedPerson(i, first, last, gender, photoIndex);
  }

  console.log('\nSeeding decisions (all seed users like the dev user)…');
  await seedDecisions(devUserId, 'Female'); // 25 women like dev user
  await seedDecisions(devUserId, 'Male'); // 25 men like dev user

  console.log('\nSeeding wingpeople relationships…');
  const wingerIds = await seedWingpeopleContacts(devUserId);

  console.log('\nSeeding Sam Taylor scenario…');
  await seedSamScenario(devUserId);

  console.log('\nSeeding winger prompt responses on dev user…');
  await seedWingerPromptResponses(devUserId, wingerIds);

  console.log('\nDone. Local DB is ready. Sign in as dev@local.test / devpassword');
}

main().catch((err) => {
  console.error('\nSeed failed:', err);
  process.exit(1);
});
