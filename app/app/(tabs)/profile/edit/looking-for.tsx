import { useState } from 'react';
import Ionicons from 'react-native-vector-icons/Ionicons';
import { useNavigation } from '@react-navigation/native';
import { useQueryClient } from '@tanstack/react-query';
import { useFormContext } from 'react-hook-form';

import {
  useGetApiDatingProfilesMeSuspense,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { updateDatingProfile } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import type { UpdateDatingProfileData, Religion, Gender } from '@/lib/api/generated/model';
import { GENDERS, RELIGIONS } from '@/constants/enums';
import { View, Text, ScrollView, SafeAreaView, Pressable, TextInput } from '@/lib/tw';
import { Sheet } from '@/components/ui/Sheet';
import { cn } from '@/lib/cn';
import { colors } from '@/constants/theme';
import { NavHeader } from '@/components/ui/NavHeader';
import { SectionLabel } from '@/components/ui/SectionLabel';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { createTypedForm } from '@/lib/forms/typed-form';

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

const RELIGIOUS_PREFS: { value: Religion | null; label: string }[] = [
  { value: null, label: 'No preference' },
  { value: 'Muslim', label: 'Must be Muslim' },
  { value: 'Christian', label: 'Must be Christian' },
  { value: 'Jewish', label: 'Must be Jewish' },
  { value: 'Hindu', label: 'Must be Hindu' },
  { value: 'Buddhist', label: 'Must be Buddhist' },
  { value: 'Sikh', label: 'Must be Sikh' },
];

type Values = {
  interestedGender: Gender[];
  ageFrom: string;
  ageTo: string;
  religion: Religion;
  religiousPref: Religion | null;
};

const LookingForForm = createTypedForm<Values>();

const ageFromRule = (v: string) => {
  if (!/^\d+$/.test(v)) return 'Enter a valid age';
  if (parseInt(v, 10) < 18) return 'Must be 18 or above';
  return true;
};
const ageToRule = (v: string, all: Values) => {
  if (!v) return true;
  if (!/^\d+$/.test(v)) return 'Enter a valid age';
  const from = parseInt(all.ageFrom, 10);
  if (!isNaN(from) && parseInt(v, 10) <= from) return 'Must be greater than From';
  return true;
};

const inputClass =
  'bg-white rounded-xl border-[1.5px] border-separator px-4 py-[14px] text-base text-fg';

// Age range lives in its own component so it can read getValues()/formState via the
// form context — saveAges only patches when both age fields are currently valid.
function AgeRange({ onSave }: { onSave: (u: UpdateDatingProfileData) => void }) {
  const { getValues, formState } = useFormContext<Values>();
  const saveAges = () => {
    const vals = getValues();
    if (formState.errors.ageFrom || formState.errors.ageTo) return;
    const from = parseInt(vals.ageFrom, 10);
    const to = vals.ageTo ? parseInt(vals.ageTo, 10) : null;
    if (!isNaN(from)) onSave({ ageFrom: from, ageTo: to });
  };
  return (
    <View className="flex-row items-start" style={{ gap: 12 }}>
      <View style={{ flex: 1 }}>
        <Text className="text-xs text-fg-muted mb-1.5">From</Text>
        <LookingForForm.CustomField
          name="ageFrom"
          bare
          rules={{ validate: ageFromRule }}
          render={({ value, onChange, invalid }) => (
            <TextInput
              className={cn(inputClass, invalid && 'border-error')}
              value={value ?? ''}
              onChangeText={onChange}
              onBlur={saveAges}
              keyboardType="number-pad"
              maxLength={2}
            />
          )}
        />
      </View>
      <View style={{ flex: 1 }}>
        <Text className="text-xs text-fg-muted mb-1.5">To (optional)</Text>
        <LookingForForm.CustomField
          name="ageTo"
          optional
          bare
          rules={{ validate: ageToRule }}
          render={({ value, onChange, invalid }) => (
            <TextInput
              className={cn(inputClass, invalid && 'border-error')}
              value={value ?? ''}
              onChangeText={onChange}
              onBlur={saveAges}
              keyboardType="number-pad"
              maxLength={2}
              placeholder="—"
            />
          )}
        />
      </View>
    </View>
  );
}

function LookingForScreenInner() {
  const navigation = useNavigation();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const [religionSheetOpen, setReligionSheetOpen] = useState(false);

  const patch = async (updates: UpdateDatingProfileData) => {
    if (!datingProfile) return;
    try {
      await updateDatingProfile(datingProfile.id, updates);
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch (err) {
      toastError(err, 'Could not save. Try again.');
    }
  };

  if (!datingProfile) return null;

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Looking for" onBack={() => navigation.goBack()} />
      <LookingForForm.Form
        mode="onChange"
        onSubmit={() => {}}
        defaultValues={{
          interestedGender: datingProfile.interestedGender ?? [],
          ageFrom: String(datingProfile.ageFrom ?? 18),
          ageTo: datingProfile.ageTo ? String(datingProfile.ageTo) : '',
          religion: datingProfile.religion ?? RELIGIONS[0],
          religiousPref: datingProfile.religiousPreference ?? null,
        }}
      >
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <SectionLabel style={sectionLabelStyle}>Interested in</SectionLabel>
          <LookingForForm.CustomField
            name="interestedGender"
            bare
            render={({ value, onChange }) => {
              const selected: Gender[] = value ?? [];
              return (
                <View className="flex-row flex-wrap" style={{ gap: 8 }}>
                  {GENDERS.map((g) => {
                    const active = selected.includes(g);
                    return (
                      <Pressable
                        key={g}
                        onPress={() => {
                          const next = active ? selected.filter((v) => v !== g) : [...selected, g];
                          onChange(next);
                          patch({ interestedGender: next });
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
                          {g}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              );
            }}
          />

          <SectionLabel style={sectionLabelStyle}>Age range</SectionLabel>
          <AgeRange onSave={patch} />

          <SectionLabel style={sectionLabelStyle}>My religion</SectionLabel>
          <LookingForForm.CustomField
            name="religion"
            bare
            render={({ value, onChange }) => (
              <View className="flex-row flex-wrap" style={{ gap: 8 }}>
                {RELIGIONS.map((r) => {
                  const active = value === r;
                  return (
                    <Pressable
                      key={r}
                      onPress={() => {
                        onChange(r);
                        patch({ religion: r });
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
                        {r}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            )}
          />

          <SectionLabel style={sectionLabelStyle}>{"Partner's religion (optional)"}</SectionLabel>
          <LookingForForm.CustomField
            name="religiousPref"
            optional
            bare
            render={({ value, onChange }) => {
              const selected = RELIGIOUS_PREFS.find((o) => o.value === value);
              return (
                <>
                  <Pressable
                    onPress={() => setReligionSheetOpen(true)}
                    className="bg-white rounded-xl border-[1.5px] border-separator flex-row items-center justify-between px-4"
                    style={{ paddingVertical: 14 }}
                  >
                    <Text className={selected ? 'text-base text-fg' : 'text-base text-fg-ghost'}>
                      {selected ? selected.label : 'No preference'}
                    </Text>
                    <Text className="text-fg-ghost">▾</Text>
                  </Pressable>
                  <Sheet
                    visible={religionSheetOpen}
                    onClose={() => setReligionSheetOpen(false)}
                    title="Partner's religion"
                    maxHeight="70%"
                  >
                    {RELIGIOUS_PREFS.map((opt) => {
                      const active = opt.value === value;
                      return (
                        <Pressable
                          key={String(opt.value)}
                          onPress={() => {
                            onChange(opt.value);
                            patch({ religiousPreference: opt.value });
                            setReligionSheetOpen(false);
                          }}
                          style={{
                            flexDirection: 'row',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            paddingVertical: 14,
                          }}
                        >
                          <Text
                            style={{
                              fontSize: 16,
                              color: active ? colors.primary : colors.ink,
                              fontWeight: active ? '600' : '400',
                            }}
                          >
                            {opt.label}
                          </Text>
                          {active ? (
                            <Ionicons name="checkmark" size={18} color={colors.primary} />
                          ) : null}
                        </Pressable>
                      );
                    })}
                  </Sheet>
                </>
              );
            }}
          />
        </ScrollView>
      </LookingForForm.Form>
    </SafeAreaView>
  );
}

export default function LookingForScreen() {
  return (
    <ScreenSuspense>
      <LookingForScreenInner />
    </ScreenSuspense>
  );
}
