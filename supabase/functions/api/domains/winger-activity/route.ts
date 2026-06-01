import type { OpenAPIHono } from '@hono/zod-openapi';
import { createRoute, z } from '@hono/zod-openapi';
import type { AppEnv } from '../../types.ts';
import {
  WingerPeopleActivityResponse,
  WingerPhotosActivityResponse,
  WingerPromptsActivityResponse,
} from './schemas.ts';
import { fetchPeopleActivity, fetchPhotosActivity, fetchPromptsActivity } from './queries.ts';
import { transformSuggestion, transformPhoto, transformPrompt } from './transformers.ts';
import { getDeps } from '../../lib/deps.ts';

const LimitQuery = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(50),
});

const peopleRoute = createRoute({
  method: 'get',
  path: '/winger-activity/people',
  tags: ['winger-activity'],
  security: [{ Bearer: [] }],
  request: { query: LimitQuery },
  responses: {
    200: {
      description: 'Profiles suggested by the winger and their match outcomes',
      content: { 'application/json': { schema: WingerPeopleActivityResponse } },
    },
    401: { description: 'Unauthenticated' },
  },
});

const photosRoute = createRoute({
  method: 'get',
  path: '/winger-activity/photos',
  tags: ['winger-activity'],
  security: [{ Bearer: [] }],
  request: { query: LimitQuery },
  responses: {
    200: {
      description: 'Photos suggested by the winger and their approval status',
      content: { 'application/json': { schema: WingerPhotosActivityResponse } },
    },
    401: { description: 'Unauthenticated' },
  },
});

const promptsRoute = createRoute({
  method: 'get',
  path: '/winger-activity/prompts',
  tags: ['winger-activity'],
  security: [{ Bearer: [] }],
  request: { query: LimitQuery },
  responses: {
    200: {
      description: 'Prompt responses suggested by the winger and their acceptance status',
      content: { 'application/json': { schema: WingerPromptsActivityResponse } },
    },
    401: { description: 'Unauthenticated' },
  },
});

export function mountWingerActivity(app: OpenAPIHono<AppEnv>) {
  app.openapi(peopleRoute, async (c) => {
    const { userId: wingerId, db } = getDeps(c);
    const { limit } = c.req.valid('query');
    const rows = await fetchPeopleActivity(db, wingerId, limit);
    return c.json(rows.map(transformSuggestion), 200);
  });

  app.openapi(photosRoute, async (c) => {
    const { userId: wingerId, db } = getDeps(c);
    const { limit } = c.req.valid('query');
    const rows = await fetchPhotosActivity(db, wingerId, limit);
    return c.json(rows.map(transformPhoto), 200);
  });

  app.openapi(promptsRoute, async (c) => {
    const { userId: wingerId, db } = getDeps(c);
    const { limit } = c.req.valid('query');
    const rows = await fetchPromptsActivity(db, wingerId, limit);
    return c.json(rows.map(transformPrompt), 200);
  });
}
