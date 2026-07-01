// Realtime new-message stream over the backend `/ws` endpoint. HTTP reads/writes
// for messages live in `lib/api/generated/messages/messages.ts`; this module only
// carries the new-message stream.

import { wsClient } from '@/lib/ws-client';
import type { Message } from '@/lib/api/generated/model';

type DbMessageRow = {
  id: string;
  match_id: string;
  sender_id: string;
  body: string;
  is_read: boolean;
  created_at: string;
};

// The payload envelope the caller destructures.
type MessageInsertPayload = { new: DbMessageRow };

export function dbRowToMessage(row: DbMessageRow): Message {
  return {
    id: row.id,
    matchId: row.match_id,
    senderId: row.sender_id,
    body: row.body,
    isRead: row.is_read,
    createdAt: row.created_at,
    sender: { id: row.sender_id, chosenName: null },
  };
}

// The WS `message` frame carries a camelCase `Message` (identical to the HTTP
// GET item). The caller's pipeline (`dbRowToMessage(payload.new)`) expects a
// snake_case row, so fold it back to that shape here — and preserve the richer
// `sender` so the chat shows the real name instead of `chosenName: null`.
function messageToDbRow(msg: Message): DbMessageRow {
  return {
    id: msg.id,
    match_id: msg.matchId,
    sender_id: msg.senderId,
    body: msg.body,
    is_read: msg.isRead,
    created_at: msg.createdAt,
  };
}

export function subscribeToMessages(
  matchId: string,
  onInsert: (payload: MessageInsertPayload) => void,
): { unsubscribe: () => void } {
  const channel = `messages:match:${matchId}`;

  const off = wsClient.subscribe(channel, (event) => {
    if (event.type !== 'message') return;
    const msg = event.payload as Message;
    onInsert({ new: messageToDbRow(msg) });
  });

  return { unsubscribe: off };
}
