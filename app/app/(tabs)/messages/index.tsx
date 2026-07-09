import { FlatList, ScrollView as RNScrollView, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';

import { useAuth } from '@/context/auth';
import { useGetApiConversationsSuspense } from '@/lib/api/generated/messages/messages';
import type { Conversation } from '@/lib/api/generated/model';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { SectionLabel } from '@/components/ui/SectionLabel';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { useMessagesListPresence } from '@/hooks/use-messages-list-presence';
import { relativeTime } from '@/lib/time';
import { View, Text, Pressable, SafeAreaView } from '@/lib/tw';

const SECTION_LABEL_STYLE = {
  fontSize: 10.5,
  letterSpacing: 1.5,
  fontWeight: '700',
  paddingHorizontal: 16,
  paddingTop: 14,
  paddingBottom: 6,
} as const;

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
          className="bg-primary border-surface"
          style={{
            position: 'absolute',
            top: -2,
            right: -2,
            width: 14,
            height: 14,
            borderRadius: 7,
            borderWidth: 2,
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
      className="flex-row items-center border-border-subtle"
      style={{
        paddingHorizontal: 16,
        paddingVertical: 12,
        gap: 12,
        borderBottomWidth: StyleSheet.hairlineWidth,
      }}
    >
      <View style={{ position: 'relative' }}>
        <FaceAvatar name={name} size={50} />
        {isOnline && (
          <View
            className="bg-green border-surface"
            style={{
              position: 'absolute',
              bottom: 1,
              right: 1,
              width: 12,
              height: 12,
              borderRadius: 6,
              borderWidth: 2,
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
            className={isUnread ? 'text-ink' : 'text-ink-dim'}
            style={{
              flex: 1,
              fontSize: 13.5,
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
      <View className="bg-border-subtle" style={{ width: 50, height: 50, borderRadius: 25 }} />
      <View style={{ flex: 1, gap: 6 }}>
        <View className="bg-border-subtle" style={{ height: 12, borderRadius: 6, width: '60%' }} />
        <View className="bg-border-subtle" style={{ height: 12, borderRadius: 6, width: '40%' }} />
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
  const navigation = useNavigation();
  const { data: convos, refetch, isRefetching } = useGetApiConversationsSuspense();

  const sayHello = convos.filter((c) => c.lastMessage == null);
  const conversations = convos.filter((c) => c.lastMessage != null);

  function openChat(convo: Conversation) {
    navigation.navigate('MessageThread', {
      matchId: convo.matchId,
      otherName: convo.other.chosenName ?? '',
      otherUserId: convo.other.id,
    });
  }

  const ListHeader = (
    <>
      <Header />
      {sayHello.length > 0 && (
        <>
          <SectionLabel style={SECTION_LABEL_STYLE}>Say hello</SectionLabel>
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
      {conversations.length > 0 && (
        <SectionLabel style={SECTION_LABEL_STYLE}>Conversations</SectionLabel>
      )}
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
