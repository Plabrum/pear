import { useEffect, useRef, useState } from 'react';
import { wsClient } from '@/lib/ws-client';

const BROADCAST_INTERVAL_MS = 2000;
const CLEAR_AFTER_MS = 3000;

/**
 * Broadcasts and listens for "typing" events on a per-pair channel.
 * Returns whether the other participant is currently typing and a `notifyTyping`
 * function to call on each composer keystroke (internally throttled).
 *
 * The server stamps the typing frame with `userId` + `ts`; incoming frames carry
 * `payload.userId`/`payload.ts`. The shared socket does not echo our own typing,
 * so the self-filter is a defensive belt-and-braces guard.
 */
export function useTyping(
  otherUserId: string | null,
  myUserId: string
): { isOtherTyping: boolean; notifyTyping: () => void } {
  const [isOtherTyping, setIsOtherTyping] = useState(false);
  const channelRef = useRef<string | null>(null);
  const lastBroadcastRef = useRef(0);
  const clearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!otherUserId || !myUserId) return;

    const channel = `typing:${[myUserId, otherUserId].sort().join(':')}`;
    channelRef.current = channel;

    const off = wsClient.subscribe(channel, (event) => {
      if (event.type !== 'typing') return;
      if (event.payload?.userId !== otherUserId) return;
      setIsOtherTyping(true);
      if (clearTimerRef.current) clearTimeout(clearTimerRef.current);
      clearTimerRef.current = setTimeout(() => setIsOtherTyping(false), CLEAR_AFTER_MS);
    });

    return () => {
      if (clearTimerRef.current) {
        clearTimeout(clearTimerRef.current);
        clearTimerRef.current = null;
      }
      off();
      channelRef.current = null;
      setIsOtherTyping(false);
      lastBroadcastRef.current = 0;
    };
  }, [otherUserId, myUserId]);

  const notifyTyping = () => {
    const channel = channelRef.current;
    if (!channel) return;
    const now = Date.now();
    if (now - lastBroadcastRef.current < BROADCAST_INTERVAL_MS) return;
    lastBroadcastRef.current = now;
    wsClient.sendTyping(channel);
  };

  return { isOtherTyping, notifyTyping };
}
