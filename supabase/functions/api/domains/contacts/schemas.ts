import { z } from '@hono/zod-openapi';
import { gender, interest } from '../../db/schema.ts';

const genderValues = gender.enumValues;
const interestValues = interest.enumValues;

export const WingerSummary = z
  .object({
    id: z.string().uuid(),
    chosenName: z.string().nullable(),
    gender: z.enum(genderValues).nullable(),
    avatarUrl: z.string().nullable(),
  })
  .openapi('WingerSummary');

export const DaterSummary = z
  .object({
    id: z.string().uuid(),
    chosenName: z.string().nullable(),
  })
  .openapi('DaterSummary');

export const WingingForDater = z
  .object({
    id: z.string().uuid(),
    chosenName: z.string().nullable(),
    avatarUrl: z.string().nullable(),
    interests: z.array(z.enum(interestValues)).nullable(),
    bio: z.string().nullable(),
    interestedGender: z.array(z.enum(genderValues)).nullable(),
  })
  .openapi('WingingForDater');

export const Wingperson = z
  .object({
    id: z.string().uuid(),
    createdAt: z.string(),
    winger: WingerSummary.nullable(),
  })
  .openapi('Wingperson');

export const IncomingInvitation = z
  .object({
    id: z.string().uuid(),
    createdAt: z.string(),
    dater: DaterSummary.nullable(),
  })
  .openapi('IncomingInvitation');

export const WingingForRow = z
  .object({
    id: z.string().uuid(),
    createdAt: z.string(),
    dater: WingingForDater.nullable(),
  })
  .openapi('WingingForRow');

export const SentInvitation = z
  .object({
    id: z.string().uuid(),
    createdAt: z.string(),
    phoneNumber: z.string(),
    winger: DaterSummary.nullable(),
  })
  .openapi('SentInvitation');

export const WingpeopleResponse = z
  .object({
    wingpeople: z.array(Wingperson),
    invitations: z.array(IncomingInvitation),
    wingingFor: z.array(WingingForRow),
    sentInvitations: z.array(SentInvitation),
    weeklyCounts: z.record(z.string().uuid(), z.number().int()),
  })
  .openapi('WingpeopleResponse');

export const InviteWingpersonRequest = z
  .object({
    phoneNumber: z.string().min(1),
  })
  .openapi('InviteWingpersonRequest');

export const InviteWingpersonResponse = z
  .object({
    id: z.string().uuid(),
    phoneNumber: z.string(),
    wingerId: z.string().uuid().nullable(),
  })
  .openapi('InviteWingpersonResponse');

export const ContactIdParam = z
  .object({ id: z.string().uuid() })
  .openapi('ContactIdParam');

export const OkResponse = z
  .object({ ok: z.literal(true) })
  .openapi('ContactsOkResponse');

export type WingpeopleResponse = z.infer<typeof WingpeopleResponse>;
export type Wingperson = z.infer<typeof Wingperson>;
export type IncomingInvitation = z.infer<typeof IncomingInvitation>;
export type WingingForRow = z.infer<typeof WingingForRow>;
export type SentInvitation = z.infer<typeof SentInvitation>;
