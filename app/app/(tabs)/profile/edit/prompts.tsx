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
import { PromptsTab } from '@/components/profile/PromptsTab';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

function PromptsScreenInner() {
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
    queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
  }, [queryClient, form]);

  if (!datingProfile) return null;

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Prompts" onBack={() => router.back()} />
      <PromptsTab form={form} onRefresh={handleRefresh} />
    </SafeAreaView>
  );
}

export default function PromptsScreen() {
  return (
    <ScreenSuspense>
      <PromptsScreenInner />
    </ScreenSuspense>
  );
}
