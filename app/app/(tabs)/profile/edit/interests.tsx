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
import { INTERESTS } from '@/constants/enums';
import { View, Text, ScrollView, SafeAreaView, Pressable } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { NavHeader } from '@/components/ui/NavHeader';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

const schema = z.object({
  interests: z.array(z.enum(INTERESTS)),
});

type Values = z.infer<typeof schema>;

function InterestsScreenInner() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const { control } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { interests: datingProfile?.interests ?? [] },
  });

  const patch = async (interests: string[]) => {
    try {
      await patchApiDatingProfilesMe({ interests: interests as Values['interests'] });
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch {
      toast.error('Could not save interests. Try again.');
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Interests" onBack={() => router.back()} />
      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
        showsVerticalScrollIndicator={false}
      >
        <Text style={{ fontSize: 13, color: 'rgba(31,27,22,0.50)', marginBottom: 14 }}>
          Pick anything that describes you. Shared interests show up on your profile.
        </Text>
        <Controller
          control={control}
          name="interests"
          render={({ field }) => (
            <View className="flex-row flex-wrap" style={{ gap: 8 }}>
              {INTERESTS.map((interest) => {
                const active = field.value.includes(interest);
                return (
                  <Pressable
                    key={interest}
                    onPress={() => {
                      const next = active
                        ? field.value.filter((v) => v !== interest)
                        : [...field.value, interest];
                      field.onChange(next);
                      patch(next);
                    }}
                    className={cn(
                      'px-4 rounded-[24px] border-[1.5px] border-separator bg-white',
                      active && 'border-accent bg-accent-muted'
                    )}
                    style={{ paddingVertical: 10 }}
                  >
                    <Text
                      className={cn('text-sm text-fg-muted font-medium', active && 'text-accent')}
                    >
                      {interest}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          )}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

export default function InterestsScreen() {
  return (
    <ScreenSuspense>
      <InterestsScreenInner />
    </ScreenSuspense>
  );
}
