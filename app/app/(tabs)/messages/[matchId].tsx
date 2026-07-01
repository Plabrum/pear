import React, { useRef, useState } from 'react';
import { FlatList, Platform, StyleSheet } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { useBottomTabBarHeight } from 'expo-router/js-tabs';
import { KeyboardAvoidingView } from 'react-native-keyboard-controller';

import { useAuth } from '@/context/auth';
import { useMessages } from '@/hooks/use-messages';
import { usePresence } from '@/hooks/use-presence';
import { useTyping } from '@/hooks/use-typing';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { BackIcon, SendIcon } from '@/components/ui/icons';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { formatTimestamp } from '@/lib/time';
import { colors } from '@/constants/theme';
import { View, Text, TextInput, Pressable, SafeAreaView } from '@/lib/tw';

// ── ChatHeader ────────────────────────────────────────────────────────────────

type ChatHeaderProps = {
  name: string;
  isOnline: boolean;
};

function ChatHeader({ name, isOnline }: ChatHeaderProps) {
  return (
    <View
      className="flex-row items-center bg-surface border-border"
      style={{
        paddingHorizontal: 16,
        paddingVertical: 8,
        gap: 10,
        borderBottomWidth: StyleSheet.hairlineWidth,
      }}
    >
      <Pressable
        onPress={() => router.back()}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        style={{ padding: 4, marginLeft: -4 }}
      >
        <BackIcon />
      </Pressable>
      <View style={{ position: 'relative' }}>
        <FaceAvatar name={name} size={36} />
        {isOnline && (
          <View
            className="bg-green border-surface"
            style={{
              position: 'absolute',
              bottom: -1,
              right: -1,
              width: 10,
              height: 10,
              borderRadius: 5,
              borderWidth: 2,
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
          backgroundColor: isMine ? colors.leaf : colors.white,
          borderWidth: isMine ? 0 : StyleSheet.hairlineWidth,
          borderColor: colors.divider,
          opacity: isOptimistic ? 0.65 : 1,
        }}
      >
        <Text
          style={{
            fontSize: 14.5,
            lineHeight: 20,
            color: isMine ? colors.white : colors.ink,
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
        className="flex-row items-center bg-surface border-border"
        style={{
          paddingHorizontal: 12,
          paddingTop: 10,
          paddingBottom: 12,
          gap: 8,
          borderTopWidth: StyleSheet.hairlineWidth,
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
                placeholderTextColor={colors.inkDim}
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
            backgroundColor: canSend ? colors.leaf : colors.muted,
          }}
        >
          <SendIcon color={canSend ? colors.white : colors.inkDim} />
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
