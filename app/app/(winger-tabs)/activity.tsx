import { useState } from 'react';
import { Image } from 'expo-image';

import { View, Text, ScrollView, SafeAreaView } from '@/lib/tw';
import { TextTabBar } from '@/components/ui/TextTabBar';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { Card } from '@/components/ui/Card';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { cn } from '@/lib/cn';
import { relativeTime } from '@/lib/time';
import { useGetApiDecisionsMySuggestionsSuspense } from '@/lib/api/generated/decisions/decisions';
import { useGetApiPhotosSuggestedSuspense } from '@/lib/api/generated/photos/photos';
import { useGetApiPromptResponsesMeSuspense } from '@/lib/api/generated/prompts/prompts';
import type {
  MySuggestion,
  SuggestedPhoto,
  AuthoredPromptResponse,
} from '@/lib/api/generated/model';

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

type ActivityMeta = { label: string; variant: PillVariant; message: string };

function peopleMeta(item: MySuggestion): ActivityMeta {
  switch (item.status) {
    case 'matched':
      return { label: 'Matched', variant: 'positive', message: 'Your pick became a match.' };
    case 'not_accepted':
      return {
        label: 'Not accepted',
        variant: 'muted',
        message: `${item.daterName} passed on ${item.suggestedName}.`,
      };
    case 'pending':
      return {
        label: 'Pending',
        variant: 'neutral',
        message: `You suggested ${item.suggestedName} — pending review.`,
      };
  }
}

function photoMeta(item: SuggestedPhoto): ActivityMeta {
  switch (item.status) {
    case 'approved':
      return { label: 'Approved', variant: 'positive', message: 'Photo suggestion was approved.' };
    case 'not_accepted':
      return {
        label: 'Not accepted',
        variant: 'muted',
        message: 'Photo suggestion was not accepted.',
      };
    case 'pending':
      return {
        label: 'Pending',
        variant: 'neutral',
        message: 'Photo suggestion pending approval.',
      };
  }
}

function promptPill(status: AuthoredPromptResponse['status']): {
  label: string;
  variant: PillVariant;
} {
  switch (status) {
    case 'accepted':
      return { label: 'Accepted', variant: 'positive' };
    case 'not_accepted':
      return { label: 'Not accepted', variant: 'muted' };
    case 'pending':
      return { label: 'Pending', variant: 'neutral' };
  }
}

function ActivityCard({ children, muted }: { children: React.ReactNode; muted?: boolean }) {
  return (
    <Card className="px-3.5 py-3" style={muted ? { opacity: 0.55 } : undefined}>
      {children}
    </Card>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <View className="mt-2 p-5 rounded-2xl bg-accent-muted border border-leaf-soft">
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
  const { data } = useGetApiDecisionsMySuggestionsSuspense();

  if (data.length === 0) {
    return <EmptyState message="Profiles you suggest as matches will appear here." />;
  }

  return (
    <View style={{ gap: 8 }}>
      {data.map((item: MySuggestion) => {
        const meta = peopleMeta(item);
        return (
          <ActivityCard key={item.id} muted={item.status === 'not_accepted'}>
            <View className="flex-row gap-3 items-start">
              <FaceAvatar name={item.daterName} size={40} />
              <View className="flex-1">
                <View className="flex-row justify-between items-start">
                  <Text className="text-sm text-fg flex-1">
                    <Text className="font-semibold">{item.daterName}</Text>
                    <Text className="text-fg-muted">{` · ${item.suggestedName}`}</Text>
                  </Text>
                  <Text className="text-xs text-fg-subtle ml-3">
                    {relativeTime(item.createdAt)}
                  </Text>
                </View>
                <Text className="text-sm mt-0.5 text-fg-muted">{meta.message}</Text>
                <StatusPill label={meta.label} variant={meta.variant} />
              </View>
            </View>
          </ActivityCard>
        );
      })}
    </View>
  );
}

function PhotosTab() {
  const { data } = useGetApiPhotosSuggestedSuspense();

  if (data.length === 0) {
    return <EmptyState message="Photos you suggest for a dater's profile will appear here." />;
  }

  return (
    <View style={{ gap: 8 }}>
      {data.map((item: SuggestedPhoto) => {
        const meta = photoMeta(item);
        const photoUrl = item.storageUrl;
        return (
          <ActivityCard key={item.id} muted={item.status === 'not_accepted'}>
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
                    {relativeTime(item.createdAt)}
                  </Text>
                </View>
                <Text className="text-sm mt-0.5 text-fg-muted">{meta.message}</Text>
                <StatusPill label={meta.label} variant={meta.variant} />
              </View>
            </View>
          </ActivityCard>
        );
      })}
    </View>
  );
}

function PromptsTab() {
  const { data } = useGetApiPromptResponsesMeSuspense();

  if (data.length === 0) {
    return <EmptyState message="Prompt responses you write for daters will appear here." />;
  }

  return (
    <View style={{ gap: 8 }}>
      {data.map((item: AuthoredPromptResponse) => {
        const pill = promptPill(item.status);
        return (
          <ActivityCard key={item.id} muted={item.status === 'not_accepted'}>
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
                  {relativeTime(item.createdAt)}
                </Text>
              </View>
            </View>
          </ActivityCard>
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
