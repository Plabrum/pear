// Realtime stays on supabase-js by design: the `api` Hono function is HTTP-only
// and the new-message stream needs WebSocket subscriptions. HTTP reads/writes
// for messages live in `lib/api/generated/messages/messages.ts`.

import type { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import type { Message } from '@/lib/api/generated/model';

type DbMessageRow = {
  id: string;
  match_id: string;
  sender_id: string;
  body: string;
  is_read: boolean;
  created_at: string;
};

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

export function subscribeToMessages(
  matchId: string,
  onInsert: (payload: RealtimePostgresChangesPayload<DbMessageRow>) => void
): RealtimeChannel {
  return supabase
    .channel(`messages:match:${matchId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'messages',
        filter: `match_id=eq.${matchId}`,
      },
      onInsert
    )
    .subscribe();
}
