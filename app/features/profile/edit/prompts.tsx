import { useNavigation } from '@react-navigation/native';
import { useForm } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';

import {
  useGetApiDatingProfilesMeSuspense,
  getApiDatingProfilesMe,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import type { OwnDatingProfile } from '@/lib/api/generated/model';
import { SafeAreaView } from '@/lib/tw';
import { NavHeader } from '@/components/NavHeader';
import { PromptsTab } from '@/features/profile/PromptsTab';
import ScreenSuspense from '@/components/ScreenSuspense';

function PromptsScreenInner() {
  const navigation = useNavigation();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const form = useForm<OwnDatingProfile>({
    defaultValues: datingProfile ?? undefined,
  });

  const handleRefresh = async () => {
    const fresh = await getApiDatingProfilesMe();
    if (fresh) {
      form.reset(fresh);
      queryClient.setQueryData(getGetApiDatingProfilesMeQueryKey(), fresh);
    }
    queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
  };

  if (!datingProfile) return null;

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Prompts" onBack={() => navigation.goBack()} />
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
