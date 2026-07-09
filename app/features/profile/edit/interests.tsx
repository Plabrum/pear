import { useNavigation } from '@react-navigation/native';
import { useQueryClient } from '@tanstack/react-query';

import {
  useGetApiDatingProfilesMeSuspense,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { updateDatingProfile } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import type { Interest } from '@/lib/api/generated/model';
import { INTERESTS } from '@/constants/enums';
import { View, Text, ScrollView, SafeAreaView, Pressable } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { NavHeader } from '@/components/NavHeader';
import ScreenSuspense from '@/components/ScreenSuspense';
import { createTypedForm } from '@/lib/forms/typed-form';

type Values = { interests: Interest[] };
const InterestsForm = createTypedForm<Values>();

function InterestsScreenInner() {
  const navigation = useNavigation();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const patch = async (interests: string[]) => {
    if (!datingProfile) return;
    try {
      await updateDatingProfile(datingProfile.id, { interests: interests as Interest[] });
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch (err) {
      toastError(err, 'Could not save interests. Try again.');
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Interests" onBack={() => navigation.goBack()} />
      <InterestsForm.Form
        defaultValues={{ interests: datingProfile?.interests ?? [] }}
        onSubmit={() => {}}
      >
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
          showsVerticalScrollIndicator={false}
        >
          <Text style={{ fontSize: 13, color: 'rgba(31,27,22,0.50)', marginBottom: 14 }}>
            Pick anything that describes you. Shared interests show up on your profile.
          </Text>
          <InterestsForm.CustomField
            name="interests"
            bare
            render={({ value, onChange }) => {
              const selected: Interest[] = value ?? [];
              return (
                <View className="flex-row flex-wrap" style={{ gap: 8 }}>
                  {INTERESTS.map((interest) => {
                    const active = selected.includes(interest);
                    return (
                      <Pressable
                        key={interest}
                        onPress={() => {
                          const next = active
                            ? selected.filter((v) => v !== interest)
                            : [...selected, interest];
                          onChange(next);
                          patch(next);
                        }}
                        className={cn(
                          'px-4 rounded-[24px] border-[1.5px] border-separator bg-white',
                          active && 'border-accent bg-accent-muted'
                        )}
                        style={{ paddingVertical: 10 }}
                      >
                        <Text
                          className={cn(
                            'text-sm text-fg-muted font-medium',
                            active && 'text-accent'
                          )}
                        >
                          {interest}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              );
            }}
          />
        </ScrollView>
      </InterestsForm.Form>
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
