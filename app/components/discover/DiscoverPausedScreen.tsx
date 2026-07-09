import { useForm } from 'react-hook-form';

import { View, Text, SafeAreaView } from '@/lib/tw';
import type { DatingStatus } from '@/lib/api/generated/model';
import { resumeDating } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import { LargeHeader } from '@/components/ui/LargeHeader';
import { Sprout } from '@/components/ui/Sprout';

export function DiscoverPausedScreen({
  status,
  datingProfileId,
  onResume,
}: {
  // The only paused dating status is `break` — "winging" is the profile role,
  // not a dating status.
  status: Exclude<DatingStatus, 'open'>;
  datingProfileId: string;
  onResume: () => void;
}) {
  const {
    handleSubmit,
    formState: { isSubmitting },
  } = useForm();

  async function resume() {
    try {
      await resumeDating(datingProfileId);
    } catch (err) {
      toastError(err, 'Something went wrong. Please try again.');
      return;
    }
    onResume();
  }

  return (
    <SafeAreaView className="flex-1 bg-background">
      <LargeHeader title="Discover" />
      <View className="flex-1 justify-center items-center p-6 gap-4">
        <Text className="text-2xl font-bold font-serif text-foreground text-center">
          You{"'"}re on a break
        </Text>
        <Text className="text-sm text-foreground-muted text-center leading-[22px]">
          Your profile is hidden while you{"'"}re on a break. Take all the time you need.
        </Text>
        <Sprout onPress={handleSubmit(resume)} loading={isSubmitting}>
          Resume Discover
        </Sprout>
      </View>
    </SafeAreaView>
  );
}
