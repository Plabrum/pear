import { useState } from 'react';
import { StyleSheet } from 'react-native';
import { Image } from 'expo-image';

import { colors } from '@/constants/theme';
import { View, Text, ScrollView, SafeAreaView } from '@/lib/tw';
import { TextTabBar } from '@/components/ui/TextTabBar';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { cn } from '@/lib/cn';
import { getPhotoUrl } from '@/lib/photos';
import {
  useGetApiWingerActivityPeopleSuspense,
  useGetApiWingerActivityPhotosSuspense,
  useGetApiWingerActivityPromptsSuspense,
} from '@/lib/api/generated/winger-activity/winger-activity';
import type {
  PeopleActivityRow,
  PhotoActivityRow,
  PromptActivityRow,
} from '@/lib/api/generated/model';

function formatRelativeTime(iso: string): string {
  const then = new Date(iso.replace(' ', 'T')).getTime();
  if (Number.isNaN(then)) return '';
  const diffMs = Date.now() - then;
  const minutes = Math.round(diffMs / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d`;
  if (days < 14) return '1w';
  const weeks = Math.round(days / 7);
  if (weeks < 5) return `${weeks}w`;
  return `${Math.round(days / 30)}mo`;
}

type PillVariant = 'positive' | 'neutral' | 'muted';

function StatusPill({ label, variant }: { label: string; variant: PillVariant }) {
  return (
    <View
      className={cn(
        'self-start rounded-full px-2.5 py-0.5 mt-2',
        variant === 'positive' ? 'bg-primary-soft' : 'bg-surface-muted'
      )}
    >
      <Text
        className={cn(
          'text-xs font-medium',
          variant === 'positive' ? 'text-primary' : 'text-fg-muted'
        )}
      >
        {label}
      </Text>
    </View>
  );
}

function Card({ children, muted }: { children: React.ReactNode; muted?: boolean }) {
  return (
    <View
      className="bg-white rounded-2xl px-3.5 py-3"
      style={{
        borderWidth: StyleSheet.hairlineWidth,
        borderColor: colors.divider,
        opacity: muted ? 0.55 : 1,
      }}
    >
      {children}
    </View>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <View
      className="mt-2 p-5 rounded-2xl bg-accent-muted"
      style={{ borderWidth: 1, borderColor: 'rgba(90,140,58,0.13)' }}
    >
      <Text className="text-xs uppercase mb-2 text-primary" style={{ letterSpacing: 1.4 }}>
        Nothing yet
      </Text>
      <Text
        className="font-serif text-fg"
        style={{ fontSize: 20, lineHeight: 26, letterSpacing: -0.3 }}
      >
        {message}
      </Text>
    </View>
  );
}

function PeopleTab() {
  const { data } = useGetApiWingerActivityPeopleSuspense();

  if (data.length === 0) {
    return <EmptyState message="Profiles you suggest as matches will appear here." />;
  }

  return (
    <View style={{ gap: 8 }}>
      {data.map((item: PeopleActivityRow) => {
        const pill =
          item.status === 'matched'
            ? { label: 'Matched', variant: 'positive' as const }
            : item.status === 'not_accepted'
              ? { label: 'Not accepted', variant: 'muted' as const }
              : { label: 'Pending', variant: 'neutral' as const };
        return (
          <Card key={item.id} muted={item.status === 'not_accepted'}>
            <View className="flex-row gap-3 items-start">
              <FaceAvatar name={item.daterName} size={40} />
              <View className="flex-1">
                <View className="flex-row justify-between items-start">
                  <Text className="text-sm text-fg flex-1">
                    <Text className="font-semibold">{item.daterName}</Text>
                    <Text className="text-fg-muted">{` · ${item.suggestedName}`}</Text>
                  </Text>
                  <Text className="text-xs text-fg-subtle ml-3">
                    {formatRelativeTime(item.createdAt)}
                  </Text>
                </View>
                <Text className="text-sm mt-0.5 text-fg-muted">
                  {item.status === 'matched'
                    ? 'Your pick became a match.'
                    : item.status === 'not_accepted'
                      ? `${item.daterName} passed on ${item.suggestedName}.`
                      : `You suggested ${item.suggestedName} — pending review.`}
                </Text>
                <StatusPill {...pill} />
              </View>
            </View>
          </Card>
        );
      })}
    </View>
  );
}

function PhotosTab() {
  const { data } = useGetApiWingerActivityPhotosSuspense();

  if (data.length === 0) {
    return <EmptyState message="Photos you suggest for a dater's profile will appear here." />;
  }

  return (
    <View style={{ gap: 8 }}>
      {data.map((item: PhotoActivityRow) => {
        const pill =
          item.status === 'approved'
            ? { label: 'Approved', variant: 'positive' as const }
            : item.status === 'not_accepted'
              ? { label: 'Not accepted', variant: 'muted' as const }
              : { label: 'Pending', variant: 'neutral' as const };
        const photoUrl = getPhotoUrl(item.storageUrl);
        return (
          <Card key={item.id} muted={item.status === 'not_accepted'}>
            <View className="flex-row gap-3 items-start">
              {photoUrl ? (
                <Image
                  source={{ uri: photoUrl }}
                  style={{ width: 56, height: 72, borderRadius: 10 }}
                  contentFit="cover"
                />
              ) : (
                <View className="rounded-xl bg-surface-muted" style={{ width: 56, height: 72 }} />
              )}
              <View className="flex-1">
                <View className="flex-row justify-between items-start">
                  <View className="flex-row items-center gap-2">
                    <FaceAvatar name={item.daterName} size={22} />
                    <Text className="text-sm text-fg">
                      <Text className="font-semibold">{item.daterName}</Text>
                      <Text className="text-fg-muted">&apos;s profile</Text>
                    </Text>
                  </View>
                  <Text className="text-xs text-fg-subtle ml-3">
                    {formatRelativeTime(item.createdAt)}
                  </Text>
                </View>
                <Text className="text-sm mt-0.5 text-fg-muted">
                  {item.status === 'approved'
                    ? 'Photo suggestion was approved.'
                    : item.status === 'not_accepted'
                      ? 'Photo suggestion was not accepted.'
                      : 'Photo suggestion pending approval.'}
                </Text>
                <StatusPill {...pill} />
              </View>
            </View>
          </Card>
        );
      })}
    </View>
  );
}

function PromptsTab() {
  const { data } = useGetApiWingerActivityPromptsSuspense();

  if (data.length === 0) {
    return <EmptyState message="Prompt responses you write for daters will appear here." />;
  }

  return (
    <View style={{ gap: 8 }}>
      {data.map((item: PromptActivityRow) => {
        const pill =
          item.status === 'accepted'
            ? { label: 'Accepted', variant: 'positive' as const }
            : item.status === 'not_accepted'
              ? { label: 'Not accepted', variant: 'muted' as const }
              : { label: 'Pending', variant: 'neutral' as const };
        return (
          <Card key={item.id} muted={item.status === 'not_accepted'}>
            <View className="flex-row gap-3 items-start">
              <FaceAvatar name={item.daterName} size={40} />
              <View className="flex-row justify-between items-start flex-1">
                <View className="flex-1">
                  <Text className="text-sm text-fg">
                    <Text className="font-semibold">{item.daterName}</Text>
                    <Text className="text-fg-muted">{` · ${item.promptQuestion}`}</Text>
                  </Text>
                  <Text className="text-sm mt-1.5 text-fg italic" style={{ lineHeight: 20 }}>
                    &ldquo;{item.message}&rdquo;
                  </Text>
                  <StatusPill {...pill} />
                </View>
                <Text className="text-xs text-fg-subtle ml-3 mt-0.5">
                  {formatRelativeTime(item.createdAt)}
                </Text>
              </View>
            </View>
          </Card>
        );
      })}
    </View>
  );
}

function ActivityContent() {
  const [tab, setTab] = useState(0);

  return (
    <>
      <View className="px-4 pt-2 pb-1">
        <Text className="font-serif text-fg" style={{ fontSize: 28, letterSpacing: -0.5 }}>
          Activity
        </Text>
      </View>
      <Text className="px-4 pb-3 text-sm text-fg-muted">Track your contributions.</Text>
      <TextTabBar tabs={['People', 'Photos', 'Prompts']} active={tab} setActive={setTab} />
      <ScrollView contentContainerClassName="px-4 pt-4 pb-32">
        {tab === 0 && (
          <ScreenSuspense>
            <PeopleTab />
          </ScreenSuspense>
        )}
        {tab === 1 && (
          <ScreenSuspense>
            <PhotosTab />
          </ScreenSuspense>
        )}
        {tab === 2 && (
          <ScreenSuspense>
            <PromptsTab />
          </ScreenSuspense>
        )}
      </ScrollView>
    </>
  );
}

export default function ActivityScreen() {
  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top']}>
      <ActivityContent />
    </SafeAreaView>
  );
}
