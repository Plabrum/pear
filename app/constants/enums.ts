import type { Database } from '@/types/database';

type City = Database['public']['Enums']['city'];
type Gender = Database['public']['Enums']['gender'];
type Religion = Database['public']['Enums']['religion'];
type Interest = Database['public']['Enums']['interest'];

export const CITIES = ['Boston', 'New York'] as const satisfies City[];

export const GENDERS = ['Male', 'Female', 'Non-Binary'] as const satisfies Gender[];

export const RELIGIONS = [
  'Muslim',
  'Christian',
  'Jewish',
  'Hindu',
  'Buddhist',
  'Sikh',
  'Agnostic',
  'Atheist',
  'Other',
  'Prefer not to say',
] as const satisfies Religion[];

export const INTERESTS = [
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
] as const satisfies Interest[];
