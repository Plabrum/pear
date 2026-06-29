import { z } from '@hono/zod-openapi';
import { city, datingStatus, gender, interest } from '../../db/schema.ts';

const genderValues = gender.enumValues;
const cityValues = city.enumValues;
const datingStatusValues = datingStatus.enumValues;
const interestValues = interest.enumValues;

export const DiscoverQuery = z.object({
  filterWingerId: z.string().uuid().optional().openapi({ example: undefined }),
  pageSize: z.coerce.number().int().min(1).max(100).default(20),
  pageOffset: z.coerce.number().int().min(0).default(0),
  wingerOnly: z.coerce.boolean().optional(),
  likesYouOnly: z.coerce.boolean().optional(),
}).openapi('DiscoverQuery');

export const WingSuggestion = z.object({
  wingerId: z.string().uuid(),
  wingerName: z.string(),
  note: z.string().nullable(),
}).openapi('WingSuggestion');

export const PromptResponse = z.object({
  wingerName: z.string(),
  message: z.string(),
}).openapi('DiscoverPromptResponse');

export const DiscoverPrompt = z.object({
  question: z.string(),
  answer: z.string(),
  responses: z.array(PromptResponse),
}).openapi('DiscoverPrompt');

export const DiscoverPhoto = z.object({
  url: z.string(),
  pickedByName: z.string().nullable(),
}).openapi('DiscoverPhoto');

export const DiscoverProfile = z.object({
  profileId: z.string().uuid(),
  userId: z.string().uuid(),
  chosenName: z.string(),
  gender: z.enum(genderValues).nullable(),
  age: z.number().int(),
  city: z.enum(cityValues),
  bio: z.string().nullable(),
  datingStatus: z.enum(datingStatusValues),
  interests: z.array(z.enum(interestValues)),
  photos: z.array(DiscoverPhoto),
  suggestions: z.array(WingSuggestion),
  prompts: z.array(DiscoverPrompt),
}).openapi('DiscoverProfile');

export const DiscoverResponse = z.array(DiscoverProfile).openapi('DiscoverResponse');

export type DiscoverProfile = z.infer<typeof DiscoverProfile>;
