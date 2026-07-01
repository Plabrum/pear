import React, { useRef, useState } from 'react';
import { FlatList, Platform, StyleSheet } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { useBottomTabBarHeight } from '@react-navigation/bottom-tabs';
import { KeyboardAvoidingView } from 'react-native-keyboard-controller';
import Svg, { Path } from 'react-native-svg';

import { useAuth } from '@/context/auth';
import { useMessages } from '@/hooks/use-messages';
import { usePresence } from '@/hooks/use-presence';
import { useTyping } from '@/hooks/use-typing';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { View, Text, TextInput, Pressable, SafeAreaView } from '@/lib/tw';

const LEAF = '#5A8C3A';
const PAPER = '#FBF8F1';
const CREAM2 = '#EDE6D6';
const INK = '#1F1B16';
const INK_SUBTLE = '#8B8170';
const LINE = 'rgba(31,27,22,0.10)';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString.replace(' ', 'T'));
  return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function BackIcon({ color = INK }: { color?: string }) {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
      <Path
        d="M15 18l-6-6 6-6"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function SendIcon({ color }: { color: string }) {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
      <Path
        d="M5 12h14M13 6l6 6-6 6"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

// ── ChatHeader ────────────────────────────────────────────────────────────────

type ChatHeaderProps = {
  name: string;
  isOnline: boolean;
};

function ChatHeader({ name, isOnline }: ChatHeaderProps) {
  return (
    <View
      className="flex-row items-center bg-surface"
      style={{
        paddingHorizontal: 16,
        paddingVertical: 8,
        gap: 10,
        borderBottomWidth: StyleSheet.hairlineWidth,
        borderBottomColor: LINE,
      }}
    >
      <Pressable
        onPress={() => router.dismiss()}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        style={{ padding: 4, marginLeft: -4 }}
      >
        <BackIcon />
      </Pressable>
      <View style={{ position: 'relative' }}>
        <FaceAvatar name={name} size={36} />
        {isOnline && (
          <View
            className="bg-green"
            style={{
              position: 'absolute',
              bottom: -1,
              right: -1,
              width: 10,
              height: 10,
              borderRadius: 5,
              borderWidth: 2,
              borderColor: PAPER,
            }}
          />
        )}
      </View>
      <View style={{ flex: 1 }}>
        <Text className="text-ink" style={{ fontSize: 15, fontWeight: '600' }} numberOfLines={1}>
          {name}
        </Text>
        <Text className="text-ink-dim" style={{ fontSize: 11.5 }} numberOfLines={1}>
          {isOnline ? 'online' : 'offline'}
        </Text>
      </View>
    </View>
  );
}

// ── MessageBubble ─────────────────────────────────────────────────────────────

type MessageBubbleProps = {
  body: string;
  isMine: boolean;
  createdAt: string;
  isOptimistic: boolean;
};

function MessageBubble({ body, isMine, createdAt, isOptimistic }: MessageBubbleProps) {
  const [showTime, setShowTime] = useState(false);

  return (
    <View
      style={{
        alignSelf: isMine ? 'flex-end' : 'flex-start',
        maxWidth: '78%',
        marginVertical: 2,
      }}
    >
      <Pressable
        onPress={() => setShowTime((v) => !v)}
        style={{
          paddingHorizontal: 13,
          paddingVertical: 8,
          borderRadius: 18,
          borderBottomRightRadius: isMine ? 5 : 18,
          borderBottomLeftRadius: isMine ? 18 : 5,
          backgroundColor: isMine ? LEAF : PAPER,
          borderWidth: isMine ? 0 : StyleSheet.hairlineWidth,
          borderColor: LINE,
          opacity: isOptimistic ? 0.65 : 1,
        }}
      >
        <Text
          style={{
            fontSize: 14.5,
            lineHeight: 20,
            color: isMine ? PAPER : INK,
          }}
        >
          {body}
        </Text>
      </Pressable>
      {showTime && (
        <Text
          className="text-ink-dim"
          style={{
            fontSize: 10.5,
            paddingHorizontal: 8,
            paddingTop: 3,
            textAlign: isMine ? 'right' : 'left',
          }}
        >
          {formatTimestamp(createdAt)}
        </Text>
      )}
    </View>
  );
}

// ── ChatBody ──────────────────────────────────────────────────────────────────

type ChatBodyProps = {
  matchId: string;
  userId: string;
  otherUserId: string | null;
  otherName: string | undefined;
};

function ChatBody({ matchId, userId, otherUserId, otherName }: ChatBodyProps) {
  const { messages, send } = useMessages(matchId);
  const { isOtherTyping, notifyTyping } = useTyping(otherUserId, userId);
  const tabBarHeight = useBottomTabBarHeight();
  const listRef = useRef<FlatList>(null);

  const {
    control,
    handleSubmit,
    reset,
    watch,
    formState: { isSubmitting },
  } = useForm<{ message: string }>({
    mode: 'onChange',
    defaultValues: { message: '' },
  });

  const messageValue = watch('message');
  const canSend = messageValue.trim().length > 0 && !isSubmitting;

  const onSubmit = handleSubmit(async ({ message }) => {
    const text = message.trim();
    if (!text) return;
    reset();
    await send(text);
    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
  });

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={tabBarHeight}
    >
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{
          flexGrow: 1,
          paddingHorizontal: 14,
          paddingVertical: 12,
          gap: 2,
        }}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
        ListEmptyComponent={
          <View className="flex-1 items-center justify-center" style={{ padding: 40 }}>
            <Text className="text-ink-dim" style={{ fontSize: 14, textAlign: 'center' }}>
              Say hello to {otherName ?? 'your match'}!
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <MessageBubble
            body={item.body}
            isMine={item.senderId === userId}
            createdAt={item.createdAt}
            isOptimistic={item.id.startsWith('temp-')}
          />
        )}
      />

      {isOtherTyping && (
        <View style={{ paddingHorizontal: 16, paddingBottom: 4 }}>
          <Text className="text-ink-dim" style={{ fontSize: 11.5, fontStyle: 'italic' }}>
            {otherName ? `${otherName} is typing…` : 'typing…'}
          </Text>
        </View>
      )}

      <View
        className="flex-row items-center bg-surface"
        style={{
          paddingHorizontal: 12,
          paddingTop: 10,
          paddingBottom: 12,
          gap: 8,
          borderTopWidth: StyleSheet.hairlineWidth,
          borderTopColor: LINE,
        }}
      >
        <View
          className="bg-canvas"
          style={{
            flex: 1,
            borderRadius: 20,
            minHeight: 40,
          }}
        >
          <Controller
            control={control}
            name="message"
            render={({ field: { value, onChange } }) => (
              <TextInput
                className="text-ink"
                style={{
                  fontSize: 14.5,
                  lineHeight: 20,
                  maxHeight: 120,
                  paddingHorizontal: 14,
                  paddingVertical: 10,
                }}
                value={value}
                onChangeText={(text) => {
                  onChange(text);
                  if (text.length > 0) notifyTyping();
                }}
                placeholder={otherName ? `Message ${otherName}…` : 'Message…'}
                placeholderTextColor={INK_SUBTLE}
                multiline
                maxLength={1000}
                returnKeyType="send"
                blurOnSubmit={false}
                onSubmitEditing={onSubmit}
              />
            )}
          />
        </View>
        {/* Sprout-styled circular send: matches prototype's ScreenChat composer */}
        <Pressable
          onPress={onSubmit}
          disabled={!canSend}
          hitSlop={6}
          className="items-center justify-center"
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            backgroundColor: canSend ? LEAF : CREAM2,
          }}
        >
          <SendIcon color={canSend ? PAPER : INK_SUBTLE} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────

export default function ChatScreen() {
  const { matchId, otherName, otherUserId } = useLocalSearchParams<{
    matchId: string;
    otherName?: string;
    otherUserId?: string;
  }>();
  const { userId } = useAuth();
  const isOnline = usePresence(otherUserId ?? null, userId);

  const headerName = otherName && otherName.length > 0 ? otherName : 'Chat';

  return (
    <SafeAreaView className="flex-1 bg-surface" edges={['top']}>
      <ChatHeader name={headerName} isOnline={isOnline} />
      <View className="flex-1 bg-canvas">
        <ScreenSuspense>
          <ChatBody
            matchId={matchId}
            userId={userId}
            otherUserId={otherUserId ?? null}
            otherName={otherName}
          />
        </ScreenSuspense>
      </View>
    </SafeAreaView>
  );
}
