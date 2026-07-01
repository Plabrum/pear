import { useRouter } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner-native';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import {
  useGetApiDatingProfilesMeSuspense,
  useGetApiProfilesMeSuspense,
  patchApiDatingProfilesMe,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { CITIES } from '@/constants/enums';
import { View, Text, ScrollView, SafeAreaView, Pressable } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { NavHeader } from '@/components/ui/NavHeader';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

const LINE = 'rgba(31,27,22,0.10)';

const schema = z.object({
  city: z.enum(CITIES),
});

type Values = z.infer<typeof schema>;

function SectionLabel({ children }: { children: string }) {
  return (
    <Text
      style={{
        fontSize: 10,
        letterSpacing: 1.2,
        textTransform: 'uppercase',
        fontWeight: '500',
        fontFamily: 'Menlo',
        color: 'rgba(31,27,22,0.45)',
        marginBottom: 10,
        marginTop: 20,
      }}
    >
      {children}
    </Text>
  );
}

function BasicsScreenInner() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const { data: profile } = useGetApiProfilesMeSuspense();

  const { control } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { city: datingProfile?.city ?? CITIES[0] },
  });

  const saveCity = async (city: string) => {
    try {
      await patchApiDatingProfilesMe({ city: city as Values['city'] });
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch {
      toast.error('Could not save city. Try again.');
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Name & basics" onBack={() => router.back()} />
      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
        showsVerticalScrollIndicator={false}
      >
        <SectionLabel>Name</SectionLabel>
        <View
          className="bg-surface"
          style={{
            borderRadius: 14,
            borderWidth: 1,
            borderColor: LINE,
            paddingHorizontal: 14,
            paddingVertical: 14,
          }}
        >
          <Text className="text-fg" style={{ fontSize: 15 }}>
            {profile?.chosenName ?? '—'}
          </Text>
          <Text style={{ fontSize: 12, color: 'rgba(31,27,22,0.40)', marginTop: 3 }}>
            Name is set during onboarding and cannot be changed here.
          </Text>
        </View>

        <SectionLabel>City</SectionLabel>
        <Controller
          control={control}
          name="city"
          render={({ field }) => (
            <View className="flex-row flex-wrap" style={{ gap: 8 }}>
              {CITIES.map((city) => {
                const active = field.value === city;
                return (
                  <Pressable
                    key={city}
                    onPress={() => {
                      field.onChange(city);
                      saveCity(city);
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
                      {city}
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

export default function BasicsScreen() {
  return (
    <ScreenSuspense>
      <BasicsScreenInner />
    </ScreenSuspense>
  );
}
