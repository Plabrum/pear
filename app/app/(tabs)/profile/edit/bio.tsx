import { useRouter } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner-native';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  useGetApiDatingProfilesMeSuspense,
  patchApiDatingProfilesMe,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { View, Text, ScrollView, SafeAreaView, TextInput } from '@/lib/tw';
import { colors } from '@/constants/theme';
import { NavHeader } from '@/components/ui/NavHeader';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

const schema = z.object({
  bio: z.string().max(500),
});

type Values = z.infer<typeof schema>;

function BioScreenInner() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const { control, getValues } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { bio: datingProfile?.bio ?? '' },
  });

  const saveBio = async () => {
    const bio = getValues('bio').trim();
    try {
      await patchApiDatingProfilesMe({ bio: bio || null });
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch {
      toast.error('Could not save bio. Try again.');
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Bio" onBack={() => router.back()} />
      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Controller
          control={control}
          name="bio"
          render={({ field }) => (
            <View>
              <TextInput
                className="bg-white rounded-xl border-[1.5px] border-separator px-4 py-[14px] text-base text-fg min-h-[140px]"
                style={{ textAlignVertical: 'top' }}
                placeholder="Tell people a bit about yourself…"
                placeholderTextColor={colors.inkGhost}
                value={field.value}
                onChangeText={field.onChange}
                onBlur={saveBio}
                multiline
                maxLength={500}
              />
              <Text className="text-xs text-fg-ghost text-right mt-1">
                {(field.value ?? '').length}/500
              </Text>
            </View>
          )}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

export default function BioScreen() {
  return (
    <ScreenSuspense>
      <BioScreenInner />
    </ScreenSuspense>
  );
}
