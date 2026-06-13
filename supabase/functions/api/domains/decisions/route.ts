import type { OpenAPIHono } from '@hono/zod-openapi';
import { createRoute } from '@hono/zod-openapi';
import { HTTPException } from 'hono/http-exception';
import type { AppEnv } from '../../types.ts';
import {
  ActSuggestionRequest,
  ActSuggestionResponse,
  DirectDecisionRequest,
  DirectDecisionResponse,
  PendingSuggestionsResponse,
  SuggestRequest,
  SuggestResponse,
  type PendingSuggestion,
} from './schemas.ts';
import {
  actOnPendingSuggestion,
  fetchPendingSuggestions,
  findMutualMatch,
  getDaterPushAndWingerName,
  getPushTokensFor,
  insertWingSuggestion,
  isActiveWingperson,
  upsertDirectDecision,
} from './queries.ts';
import { rowToMatch, rowToPendingSuggestion } from './transformers.ts';
import type { DBOrTx } from '../../db/client.ts';
import type { PushClient } from '../../lib/push.ts';
import { getDeps } from '../../lib/deps.ts';

const MATCH_PUSH_TITLE = "It's a Match! 🎉";
const MATCH_PUSH_BODY = 'You have a new match. Say hello!';

async function pushMatchCreated(
  db: DBOrTx,
  push: PushClient,
  userAId: string,
  userBId: string,
): Promise<void> {
  const tokens = await getPushTokensFor(db, [userAId, userBId]);
  await Promise.all(
    tokens.map((row) => push.send(row.pushToken, MATCH_PUSH_TITLE, MATCH_PUSH_BODY)),
  );
}

const directDecisionRoute = createRoute({
  method: 'post',
  path: '/decisions',
  tags: ['decisions'],
  security: [{ Bearer: [] }],
  request: {
    body: { content: { 'application/json': { schema: DirectDecisionRequest } }, required: true },
  },
  responses: {
    200: {
      description: 'Decision recorded',
      content: { 'application/json': { schema: DirectDecisionResponse } },
    },
    400: { description: 'Invalid input' },
    401: { description: 'Unauthenticated' },
  },
});

const actSuggestionRoute = createRoute({
  method: 'post',
  path: '/decisions/suggestions/act',
  tags: ['decisions'],
  security: [{ Bearer: [] }],
  request: {
    body: { content: { 'application/json': { schema: ActSuggestionRequest } }, required: true },
  },
  responses: {
    200: {
      description: 'Suggestion acted on',
      content: { 'application/json': { schema: ActSuggestionResponse } },
    },
    401: { description: 'Unauthenticated' },
    404: { description: 'No pending suggestion to act on' },
  },
});

const suggestRoute = createRoute({
  method: 'post',
  path: '/decisions/suggestions',
  tags: ['decisions'],
  security: [{ Bearer: [] }],
  request: {
    body: { content: { 'application/json': { schema: SuggestRequest } }, required: true },
  },
  responses: {
    200: {
      description: 'Suggestion created',
      content: { 'application/json': { schema: SuggestResponse } },
    },
    400: { description: 'Invalid input' },
    401: { description: 'Unauthenticated' },
    403: { description: 'Caller is not an active wingperson for this dater' },
  },
});

const pendingSuggestionsRoute = createRoute({
  method: 'get',
  path: '/decisions/pending-suggestions',
  tags: ['decisions'],
  security: [{ Bearer: [] }],
  responses: {
    200: {
      description: 'Pending suggestions awaiting the viewer',
      content: { 'application/json': { schema: PendingSuggestionsResponse } },
    },
    401: { description: 'Unauthenticated' },
  },
});

export function mountDecisions(app: OpenAPIHono<AppEnv>) {
  app.openapi(directDecisionRoute, async (c) => {
    const { userId: actorId, db, push } = getDeps(c);
    const { recipientId, decision } = c.req.valid('json');

    if (actorId === recipientId) {
      throw new HTTPException(400, { message: 'Cannot decide on yourself' });
    }

    const matchBefore = await findMutualMatch(db, actorId, recipientId);
    await upsertDirectDecision(db, actorId, recipientId, decision);
    const matchAfter = await findMutualMatch(db, actorId, recipientId);

    const created = matchBefore == null && matchAfter != null;
    const match = matchAfter != null ? rowToMatch(matchAfter) : null;

    if (created && matchAfter) {
      await pushMatchCreated(db, push, matchAfter.user_a_id, matchAfter.user_b_id);
    }

    return c.json({ created, match }, 200);
  });

  app.openapi(actSuggestionRoute, async (c) => {
    const { userId: actorId, db, push } = getDeps(c);
    const { recipientId, decision } = c.req.valid('json');

    const { updated } = await actOnPendingSuggestion(db, actorId, recipientId, decision);
    if (!updated) {
      throw new HTTPException(404, { message: 'No pending suggestion to act on' });
    }

    const matchRow = await findMutualMatch(db, actorId, recipientId);

    if (matchRow) {
      await pushMatchCreated(db, push, matchRow.user_a_id, matchRow.user_b_id);
    }

    return c.json({ match: matchRow != null ? rowToMatch(matchRow) : null }, 200);
  });

  app.openapi(suggestRoute, async (c) => {
    const { userId: wingerId, db, push } = getDeps(c);
    const { daterId, recipientId, note, decision } = c.req.valid('json');

    if (daterId === recipientId) {
      throw new HTTPException(400, { message: 'Cannot suggest the dater to themselves' });
    }

    const allowed = await isActiveWingperson(db, daterId, wingerId);
    if (!allowed) {
      throw new HTTPException(403, { message: 'No active wingperson relationship' });
    }

    const { inserted } = await insertWingSuggestion(
      db,
      daterId,
      recipientId,
      wingerId,
      note ?? null,
      decision,
    );

    // Only notify on a genuinely new suggestion — a no-op conflict (the dater
    // already decided on, or was already suggested, this recipient) must not
    // fire a push or imply a write happened.
    if (inserted && decision == null) {
      const { daterToken, wingerName } = await getDaterPushAndWingerName(db, daterId, wingerId);
      await push.send(
        daterToken,
        'New profile suggestion 👀',
        `${wingerName ?? 'Your wingperson'} suggested a profile for you to check out.`,
      );
    }

    return c.json({ ok: true } as const, 200);
  });

  app.openapi(pendingSuggestionsRoute, async (c) => {
    const { userId, db } = getDeps(c);
    const rows = await fetchPendingSuggestions(db, userId);
    const body: PendingSuggestion[] = rows.map(rowToPendingSuggestion);
    return c.json(body, 200);
  });
}
