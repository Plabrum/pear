import React, { useMemo } from 'react';
import { FlatList, ScrollView as RNScrollView, StyleSheet } from 'react-native';
import { router } from 'expo-router';

import { useAuth } from '@/context/auth';
import { useGetApiConversationsSuspense } from '@/lib/api/generated/messages/messages';
import type { Conversation } from '@/lib/api/generated/model';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { useMessagesListPresence } from '@/hooks/use-messages-list-presence';
import { View, Text, Pressable, SafeAreaView } from '@/lib/tw';

const PAPER = '#FBF8F1';
const INK = '#1F1B16';
const INK_SUBTLE = '#8B8170';
const LINE2 = 'rgba(31,27,22,0.06)';

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString.replace(' ', 'T')).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(isoString.replace(' ', 'T')).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

// ── SectionLabel ──────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: string }) {
  return (
    <Text
      className="text-ink-dim"
      style={{
        fontSize: 10.5,
        letterSpacing: 1.5,
        textTransform: 'uppercase',
        fontWeight: '700',
        paddingHorizontal: 16,
        paddingTop: 14,
        paddingBottom: 6,
      }}
    >
      {children}
    </Text>
  );
}

// ── SayHelloItem ──────────────────────────────────────────────────────────────

type SayHelloItemProps = {
  convo: Conversation;
  onPress: () => void;
};

function SayHelloItem({ convo, onPress }: SayHelloItemProps) {
  const name = convo.other.chosenName ?? '';
  return (
    <Pressable onPress={onPress} className="items-center" style={{ width: 70, gap: 6 }}>
      <View style={{ position: 'relative' }}>
        <FaceAvatar name={name} size={62} />
        <View
          className="bg-primary"
          style={{
            position: 'absolute',
            top: -2,
            right: -2,
            width: 14,
            height: 14,
            borderRadius: 7,
            borderWidth: 2,
            borderColor: PAPER,
          }}
        />
      </View>
      <Text className="text-ink" style={{ fontSize: 12.5, fontWeight: '500' }} numberOfLines={1}>
        {name}
      </Text>
    </Pressable>
  );
}

// ── ConvoRow ──────────────────────────────────────────────────────────────────

type ConvoRowProps = {
  convo: Conversation;
  userId: string;
  isOnline: boolean;
  onPress: () => void;
};

function ConvoRow({ convo, userId, isOnline, onPress }: ConvoRowProps) {
  const { other, lastMessage } = convo;
  const isUnread = lastMessage != null && lastMessage.senderId !== userId && !lastMessage.isRead;
  const name = other.chosenName ?? 'Someone';

  return (
    <Pressable
      onPress={onPress}
      className="flex-row items-center"
      style={{
        paddingHorizontal: 16,
        paddingVertical: 12,
        gap: 12,
        borderBottomWidth: StyleSheet.hairlineWidth,
        borderBottomColor: LINE2,
      }}
    >
      <View style={{ position: 'relative' }}>
        <FaceAvatar name={name} size={50} />
        {isOnline && (
          <View
            className="bg-green"
            style={{
              position: 'absolute',
              bottom: 1,
              right: 1,
              width: 12,
              height: 12,
              borderRadius: 6,
              borderWidth: 2,
              borderColor: PAPER,
            }}
          />
        )}
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <View className="flex-row items-baseline" style={{ justifyContent: 'space-between' }}>
          <Text
            className="text-ink"
            style={{ fontSize: 15, fontWeight: '600', flexShrink: 1 }}
            numberOfLines={1}
          >
            {name}
          </Text>
          {lastMessage != null && (
            <Text className="text-ink-dim" style={{ fontSize: 12, marginLeft: 8 }}>
              {relativeTime(lastMessage.createdAt)}
            </Text>
          )}
        </View>
        <View className="flex-row items-center" style={{ gap: 6, marginTop: 2 }}>
          <Text
            style={{
              flex: 1,
              fontSize: 13.5,
              color: isUnread ? INK : INK_SUBTLE,
              fontWeight: isUnread ? '600' : '400',
            }}
            numberOfLines={1}
          >
            {lastMessage != null
              ? `${lastMessage.senderId === userId ? 'You: ' : ''}${lastMessage.body}`
              : 'New match — say hello!'}
          </Text>
          {isUnread && (
            <View className="bg-primary" style={{ width: 8, height: 8, borderRadius: 4 }} />
          )}
        </View>
      </View>
    </Pressable>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <View
      className="flex-row items-center"
      style={{ paddingHorizontal: 16, paddingVertical: 12, gap: 12 }}
    >
      <View style={{ width: 50, height: 50, borderRadius: 25, backgroundColor: LINE2 }} />
      <View style={{ flex: 1, gap: 6 }}>
        <View style={{ height: 12, borderRadius: 6, backgroundColor: LINE2, width: '60%' }} />
        <View style={{ height: 12, borderRadius: 6, backgroundColor: LINE2, width: '40%' }} />
      </View>
    </View>
  );
}

// ── Header ────────────────────────────────────────────────────────────────────

function Header() {
  return (
    <View style={{ paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6 }}>
      <Text
        className="text-ink"
        style={{ fontFamily: 'DMSerifDisplay', fontSize: 28, letterSpacing: -0.5 }}
      >
        Messages
      </Text>
    </View>
  );
}

// ── MessagesContent ───────────────────────────────────────────────────────────

type ContentProps = {
  userId: string;
  onlineIds: Set<string>;
};

function MessagesContent({ userId, onlineIds }: ContentProps) {
  const { data: convos, refetch, isRefetching } = useGetApiConversationsSuspense();

  const { sayHello, conversations } = useMemo(() => {
    return {
      sayHello: convos.filter((c) => c.lastMessage == null),
      conversations: convos.filter((c) => c.lastMessage != null),
    };
  }, [convos]);

  function openChat(convo: Conversation) {
    router.push({
      pathname: '/(tabs)/messages/[matchId]',
      params: {
        matchId: convo.matchId,
        otherName: convo.other.chosenName ?? '',
        otherUserId: convo.other.id,
      },
    } as never);
  }

  const ListHeader = (
    <>
      <Header />
      {sayHello.length > 0 && (
        <>
          <SectionLabel>Say hello</SectionLabel>
          <RNScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{
              paddingHorizontal: 16,
              paddingTop: 6,
              paddingBottom: 14,
              gap: 14,
            }}
          >
            {sayHello.map((c) => (
              <SayHelloItem key={c.matchId} convo={c} onPress={() => openChat(c)} />
            ))}
          </RNScrollView>
        </>
      )}
      {conversations.length > 0 && <SectionLabel>Conversations</SectionLabel>}
    </>
  );

  return (
    <FlatList
      data={conversations}
      keyExtractor={(item) => item.matchId}
      onRefresh={refetch}
      refreshing={isRefetching}
      ListHeaderComponent={ListHeader}
      ListEmptyComponent={
        sayHello.length === 0 ? (
          <View className="items-center justify-center" style={{ padding: 40, paddingTop: 80 }}>
            <Text
              className="text-ink-dim"
              style={{ fontSize: 14, textAlign: 'center', lineHeight: 22 }}
            >
              No conversations yet. Start one from your Matches.
            </Text>
          </View>
        ) : null
      }
      renderItem={({ item }) => (
        <ConvoRow
          convo={item}
          userId={userId}
          isOnline={onlineIds.has(item.other.id)}
          onPress={() => openChat(item)}
        />
      )}
      contentContainerStyle={{ flexGrow: 1, paddingBottom: 100 }}
    />
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────

export default function MessagesScreen() {
  const { userId } = useAuth();
  const onlineIds = useMessagesListPresence(userId);

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top']}>
      <ScreenSuspense
        fallback={
          <>
            <Header />
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </>
        }
      >
        <MessagesContent userId={userId} onlineIds={onlineIds} />
      </ScreenSuspense>
    </SafeAreaView>
  );
}
