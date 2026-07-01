import { useEffect, useState } from 'react';
import { wsClient } from '@/lib/ws-client';

/**
 * Tracks which users are currently online for the messages-list screen.
 *
 * Connecting the shared `/ws` socket marks us online; we subscribe to the
 * `presence:messages-list` channel and read the full `onlineIds` set from
 * incoming frames (the server already excludes self where applicable).
 *
 * The useEffect is acceptable — a mount-only guard for a genuine external
 * event (the WS subscription lifecycle), matching use-presence.ts.
 */
export function useMessagesListPresence(userId: string): Set<string> {
  const [onlineIds, setOnlineIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!userId) return;

    const channel = 'presence:messages-list';

    const off = wsClient.subscribe(channel, (event) => {
      if (event.type !== 'presence' || !('onlineIds' in event)) return;
      // Defensively drop self in case the server includes it.
      setOnlineIds(new Set(event.onlineIds.filter((id) => id !== userId)));
    });

    return () => {
      off();
      setOnlineIds(new Set());
    };
  }, [userId]);

  return onlineIds;
}
