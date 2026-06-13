import { z } from '@hono/zod-openapi';

export const PeopleActivityStatus = z
  .enum(['matched', 'pending', 'not_accepted'])
  .openapi('PeopleActivityStatus');

export const PeopleActivityRow = z
  .object({
    id: z.string(),
    daterId: z.string().uuid(),
    daterName: z.string(),
    suggestedName: z.string(),
    status: PeopleActivityStatus,
    createdAt: z.string(),
  })
  .openapi('PeopleActivityRow');

export const PhotoActivityStatus = z
  .enum(['approved', 'pending', 'not_accepted'])
  .openapi('PhotoActivityStatus');

export const PhotoActivityRow = z
  .object({
    id: z.string().uuid(),
    daterId: z.string().uuid(),
    daterName: z.string(),
    storageUrl: z.string(),
    status: PhotoActivityStatus,
    createdAt: z.string(),
  })
  .openapi('PhotoActivityRow');

export const PromptActivityStatus = z
  .enum(['accepted', 'pending', 'not_accepted'])
  .openapi('PromptActivityStatus');

export const PromptActivityRow = z
  .object({
    id: z.string().uuid(),
    daterId: z.string().uuid(),
    daterName: z.string(),
    promptQuestion: z.string(),
    message: z.string(),
    status: PromptActivityStatus,
    createdAt: z.string(),
  })
  .openapi('PromptActivityRow');

export const WingerPeopleActivityResponse = z
  .array(PeopleActivityRow)
  .openapi('WingerPeopleActivityResponse');

export const WingerPhotosActivityResponse = z
  .array(PhotoActivityRow)
  .openapi('WingerPhotosActivityResponse');

export const WingerPromptsActivityResponse = z
  .array(PromptActivityRow)
  .openapi('WingerPromptsActivityResponse');

export type PeopleActivityRow = z.infer<typeof PeopleActivityRow>;
export type PhotoActivityRow = z.infer<typeof PhotoActivityRow>;
export type PromptActivityRow = z.infer<typeof PromptActivityRow>;
