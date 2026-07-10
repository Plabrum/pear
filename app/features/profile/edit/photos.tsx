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
import { PhotosTab } from '@/features/profile/PhotosTab';
import ScreenSuspense from '@/components/ScreenSuspense';

function PhotosScreenInner() {
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
  };

  if (!datingProfile) return null;

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Photos" onBack={() => navigation.goBack()} />
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
