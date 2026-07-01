import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/context/auth';
import { useGetApiMatchesMatchIdMessagesSuspense } from '@/lib/api/generated/messages/messages';
import type { Message } from '@/lib/api/generated/model';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import type { ActionDTO } from '@/lib/actions/types';
import { dbRowToMessage, subscribeToMessages } from '@/lib/messages-realtime';

// send / mark_read are object actions on the Match (message_actions). The chat
// screen reads the thread, not the Match row, so there's no actions[] to look up —
// we name the two actions directly for imperative writes. The executor invalidates
// /conversations (unread + last message) on every send/read.
const SEND: ActionDTO = {
  action: 'message_actions__send',
  label: 'Send',
  action_group_type: 'message_actions',
};
const MARK_READ: ActionDTO = {
  action: 'message_actions__mark_read',
  label: 'Mark read',
  action_group_type: 'message_actions',
};

export function useMessages(matchId: string) {
  const { userId } = useAuth();

  const { data: initial } = useGetApiMatchesMatchIdMessagesSuspense(matchId);

  const [messages, setMessages] = useState<Message[]>(initial);

  const optimisticIds = useRef<Set<string>>(new Set());

  const executor = useActionExecutor({ actionGroup: 'message_actions', objectId: matchId });

  const markRead = () => {
    void executor.executeAction(MARK_READ, undefined, { objectId: matchId, silent: true }).catch(() => {});
  };

  // Acceptable exception: mount-only side-effect kicking off a fire-and-forget
  // mark-read when the chat opens. The matchId is stable for the component lifetime.
  useEffect(() => {
    markRead();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId]);

  // Acceptable exception: mount-only guard for a genuine external event
  // (the realtime message stream). Tears down on unmount.
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
        markRead();
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

    const ok = await executor
      .executeAction(SEND, { action: SEND.action, data: { body: trimmed } }, { objectId: matchId, silent: true })
      .then(() => true)
      .catch(() => false);

    if (!ok) {
      optimisticIds.current.delete(tempId);
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
    }
  }

  return { messages, send };
}
