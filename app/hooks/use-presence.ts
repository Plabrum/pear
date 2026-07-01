import { useEffect, useRef, useState } from 'react';
import { supabase } from '@/lib/supabase';

/**
 * Tracks whether `otherUserId` is currently online using Supabase Realtime Presence.
 * Also broadcasts our own presence on the same channel so the other side can see us.
 */
export function usePresence(otherUserId: string | null, myUserId: string): boolean {
  const [isOnline, setIsOnline] = useState(false);
  const channelRef = useRef<ReturnType<typeof supabase.channel> | null>(null);

  useEffect(() => {
    if (!otherUserId || !myUserId) return;

    const channelName = `presence:${[myUserId, otherUserId].sort().join(':')}`;
    const channel = supabase.channel(channelName, {
      config: { presence: { key: myUserId } },
    });
    channelRef.current = channel;

    channel
      .on('presence', { event: 'sync' }, () => {
        const state = channel.presenceState<{ user_id: string }>();
        const online = Object.values(state).some((presences) =>
          presences.some((p) => p.user_id === otherUserId),
        );
        setIsOnline(online);
      })
      .subscribe(async (status) => {
        if (status === 'SUBSCRIBED') {
          await channel.track({ user_id: myUserId });
        }
      });

    return () => {
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [otherUserId, myUserId]);

  return isOnline;
}
