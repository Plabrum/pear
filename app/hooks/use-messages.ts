import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/context/auth';
import {
  useGetApiMatchesMatchIdMessagesSuspense,
  usePostApiMatchesMatchIdMessages,
  usePostApiMatchesMatchIdMessagesRead,
} from '@/lib/api/generated/messages/messages';
import type { Message } from '@/lib/api/generated/model';
import { dbRowToMessage, subscribeToMessages } from '@/lib/messages-realtime';

export function useMessages(matchId: string) {
  const { userId } = useAuth();

  const { data: initial } = useGetApiMatchesMatchIdMessagesSuspense(matchId);

  const [messages, setMessages] = useState<Message[]>(initial);

  const optimisticIds = useRef<Set<string>>(new Set());

  const sendMutation = usePostApiMatchesMatchIdMessages();
  const markReadMutation = usePostApiMatchesMatchIdMessagesRead();

  // Acceptable exception: mount-only side-effect kicking off a fire-and-forget
  // mark-read mutation when the chat opens. The matchId is stable for the
  // component lifetime.
  useEffect(() => {
    markReadMutation.mutate({ matchId });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  // Acceptable exception: mount-only guard for a genuine external event
  // (Supabase realtime). Tears down on unmount.
  useEffect(() => {
    if (!matchId) return;

    const channel = subscribeToMessages(matchId, (payload) => {
      const incoming = dbRowToMessage(payload.new as Parameters<typeof dbRowToMessage>[0]);

      setMessages((prev) => {
        if (incoming.senderId === userId && optimisticIds.current.size > 0) {
          const firstOptimistic = [...optimisticIds.current][0];
          optimisticIds.current.delete(firstOptimistic);
          return prev.map((m) => (m.id === firstOptimistic ? incoming : m));
        }
        if (prev.some((m) => m.id === incoming.id)) return prev;
        return [...prev, incoming];
      });

      if (incoming.senderId !== userId) {
        markReadMutation.mutate({ matchId });
      }
    });

    return () => {
      channel.unsubscribe();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId, userId]);

  async function send(body: string) {
    const trimmed = body.trim();
    if (!trimmed) return;

    const tempId = `temp-${Date.now()}`;
    optimisticIds.current.add(tempId);

    const optimistic: Message = {
      id: tempId,
      matchId,
      senderId: userId,
      body: trimmed,
      isRead: false,
      createdAt: new Date().toISOString(),
      sender: { id: userId, chosenName: null },
    };

    setMessages((prev) => [...prev, optimistic]);

    const result = await sendMutation
      .mutateAsync({ matchId, data: { body: trimmed } })
      .catch(() => null);

    if (result == null) {
      optimisticIds.current.delete(tempId);
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
    }
  }

  return { messages, send };
}
