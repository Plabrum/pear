import { useEffect, useRef, useState } from 'react';
import { supabase } from '@/lib/supabase';

/**
 * Tracks which users are currently online using a single broad Supabase Realtime
 * Presence channel for the messages list screen.
 *
 * The useEffect here is acceptable — it's a mount-only guard for a genuine external
 * event (Realtime subscription), matching the pattern in use-presence.ts.
 */
export function useMessagesListPresence(userId: string): Set<string> {
  const [onlineIds, setOnlineIds] = useState<Set<string>>(new Set());
  const channelRef = useRef<ReturnType<typeof supabase.channel> | null>(null);

  useEffect(() => {
    if (!userId) return;

    const channel = supabase.channel('presence:messages-list', {
      config: { presence: { key: userId } },
    });
    channelRef.current = channel;

    channel
      .on('presence', { event: 'sync' }, () => {
        const state = channel.presenceState<{ user_id: string }>();
        const ids = new Set<string>();
        for (const presences of Object.values(state)) {
          for (const p of presences) {
            if (p.user_id !== userId) ids.add(p.user_id);
          }
        }
        setOnlineIds(ids);
      })
      .subscribe(async (status) => {
        if (status === 'SUBSCRIBED') {
          await channel.track({ user_id: userId });
        }
      });

    return () => {
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [userId]);

  return onlineIds;
}
