import { useEffect, useState } from 'react';
import { wsClient } from '@/lib/ws-client';

/**
 * Tracks whether `otherUserId` is currently online.
 *
 * Simply connecting the shared `/ws` socket marks us online server-side (no
 * manual `track()`); to read the peer's green dot we subscribe to the per-pair
 * presence channel and consume the `online` boolean from incoming frames.
 *
 * The useEffect is acceptable — a mount-only guard for a genuine external
 * event (the WS subscription lifecycle).
 */
export function usePresence(otherUserId: string | null, myUserId: string): boolean {
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    if (!otherUserId || !myUserId) return;

    const channel = `presence:${[myUserId, otherUserId].sort().join(':')}`;

    const off = wsClient.subscribe(channel, (event) => {
      if (event.type === 'presence' && 'online' in event) {
        setIsOnline(event.online);
        return;
      }
      // Lost the channel (e.g. denied/error) — treat the peer as offline.
      if (event.type === 'error') setIsOnline(false);
    });

    return () => {
      off();
      setIsOnline(false);
    };
  }, [otherUserId, myUserId]);

  return isOnline;
}
