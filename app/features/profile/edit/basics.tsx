import { useNavigation } from '@react-navigation/native';
import { useQueryClient } from '@tanstack/react-query';

import {
  useGetApiDatingProfilesMeSuspense,
  useGetApiProfilesMeSuspense,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { updateDatingProfile } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import type { City } from '@/lib/api/generated/model';
import { CITIES } from '@/constants/enums';
import { View, Text, ScrollView, SafeAreaView, Pressable } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { colors } from '@/constants/theme';
import { NavHeader } from '@/components/NavHeader';
import { SectionLabel } from '@/components/SectionLabel';
import ScreenSuspense from '@/components/ScreenSuspense';
import { createTypedForm } from '@/lib/forms/typed-form';

type Values = { city: City };
const BasicsForm = createTypedForm<Values>();

// Preserve this screen's tighter monospace section heading look.
const sectionLabelStyle = {
  fontSize: 10,
  letterSpacing: 1.2,
  fontWeight: '500' as const,
  fontFamily: 'Menlo',
  color: 'rgba(31,27,22,0.45)',
  marginBottom: 10,
  marginTop: 20,
  paddingHorizontal: 0,
  paddingTop: 0,
  paddingBottom: 0,
};

function BasicsScreenInner() {
  const navigation = useNavigation();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const { data: profile } = useGetApiProfilesMeSuspense();

  const saveCity = async (city: string) => {
    if (!datingProfile) return;
    try {
      await updateDatingProfile(datingProfile.id, { city: city as City });
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch (err) {
      toastError(err, 'Could not save city. Try again.');
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Name & basics" onBack={() => navigation.goBack()} />
      <BasicsForm.Form
        defaultValues={{ city: datingProfile?.city ?? CITIES[0] }}
        onSubmit={() => {}}
      >
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
          showsVerticalScrollIndicator={false}
        >
          <SectionLabel style={sectionLabelStyle}>Name</SectionLabel>
          <View
            className="bg-surface"
            style={{
              borderRadius: 14,
              borderWidth: 1,
              borderColor: colors.divider,
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

          <SectionLabel style={sectionLabelStyle}>City</SectionLabel>
          <BasicsForm.CustomField
            name="city"
            bare
            render={({ value, onChange }) => (
              <View className="flex-row flex-wrap" style={{ gap: 8 }}>
                {CITIES.map((city) => {
                  const active = value === city;
                  return (
                    <Pressable
                      key={city}
                      onPress={() => {
                        onChange(city);
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
      </BasicsForm.Form>
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
