import { useEffect, useRef, useState } from 'react';
import { supabase } from '@/lib/supabase';

const BROADCAST_INTERVAL_MS = 2000;
const CLEAR_AFTER_MS = 3000;

type TypingPayload = { user_id: string; ts: number };

/**
 * Broadcasts and listens for "typing" events on a per-match Realtime channel.
 * Returns whether the other participant is currently typing and a `notifyTyping`
 * function to call on each composer keystroke (internally throttled).
 */
export function useTyping(
  otherUserId: string | null,
  myUserId: string
): { isOtherTyping: boolean; notifyTyping: () => void } {
  const [isOtherTyping, setIsOtherTyping] = useState(false);
  const channelRef = useRef<ReturnType<typeof supabase.channel> | null>(null);
  const lastBroadcastRef = useRef(0);
  const clearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!otherUserId || !myUserId) return;

    const channelName = `typing:${[myUserId, otherUserId].sort().join(':')}`;
    const channel = supabase.channel(channelName, {
      config: { broadcast: { self: false } },
    });
    channelRef.current = channel;

    channel
      .on('broadcast', { event: 'typing' }, ({ payload }: { payload: TypingPayload }) => {
        if (payload?.user_id !== otherUserId) return;
        setIsOtherTyping(true);
        if (clearTimerRef.current) clearTimeout(clearTimerRef.current);
        clearTimerRef.current = setTimeout(() => setIsOtherTyping(false), CLEAR_AFTER_MS);
      })
      .subscribe();

    return () => {
      if (clearTimerRef.current) {
        clearTimeout(clearTimerRef.current);
        clearTimerRef.current = null;
      }
      channel.unsubscribe();
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
    channel.send({
      type: 'broadcast',
      event: 'typing',
      payload: { user_id: myUserId, ts: now } satisfies TypingPayload,
    });
  };

  return { isOtherTyping, notifyTyping };
}
