import { useCallback } from 'react';
import { useRouter } from 'expo-router';
import { useForm } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';

import {
  useGetApiDatingProfilesMeSuspense,
  getApiDatingProfilesMe,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import type { OwnDatingProfileResponse } from '@/lib/api/generated/model';
import { SafeAreaView } from '@/lib/tw';
import { NavHeader } from '@/components/ui/NavHeader';
import { PhotosTab } from '@/components/profile/PhotosTab';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

function PhotosScreenInner() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const form = useForm<NonNullable<OwnDatingProfileResponse>>({
    defaultValues: datingProfile ?? undefined,
  });

  const handleRefresh = useCallback(async () => {
    const fresh = await getApiDatingProfilesMe();
    if (fresh) {
      form.reset(fresh);
      queryClient.setQueryData(getGetApiDatingProfilesMeQueryKey(), fresh);
    }
  }, [queryClient, form]);

  if (!datingProfile) return null;

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Photos" onBack={() => router.back()} />
      <PhotosTab form={form} data={datingProfile} onRefresh={handleRefresh} />
    </SafeAreaView>
  );
}

export default function PhotosScreen() {
  return (
    <ScreenSuspense>
      <PhotosScreenInner />
    </ScreenSuspense>
  );
}
