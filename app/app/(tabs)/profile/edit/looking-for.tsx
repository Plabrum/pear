import { useState } from 'react';
import { StyleSheet } from 'react-native';
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
import type { Database } from '@/types/database';
import { GENDERS, RELIGIONS } from '@/constants/enums';
import { View, Text, ScrollView, SafeAreaView, Pressable, TextInput, Modal } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { colors } from '@/constants/theme';
import { NavHeader } from '@/components/ui/NavHeader';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

type Religion = Database['public']['Enums']['religion'];

const RELIGIOUS_PREFS: { value: Religion | null; label: string }[] = [
  { value: null, label: 'No preference' },
  { value: 'Muslim', label: 'Must be Muslim' },
  { value: 'Christian', label: 'Must be Christian' },
  { value: 'Jewish', label: 'Must be Jewish' },
  { value: 'Hindu', label: 'Must be Hindu' },
  { value: 'Buddhist', label: 'Must be Buddhist' },
  { value: 'Sikh', label: 'Must be Sikh' },
];

const schema = z
  .object({
    interestedGender: z.array(z.enum(GENDERS)),
    ageFrom: z
      .string()
      .regex(/^\d+$/, 'Enter a valid age')
      .refine((v) => parseInt(v, 10) >= 18, 'Must be 18 or above'),
    ageTo: z.union([z.literal(''), z.string().regex(/^\d+$/, 'Enter a valid age')]),
    religion: z.enum(RELIGIONS),
    religiousPref: z.enum(RELIGIONS).nullable(),
  })
  .superRefine((data, ctx) => {
    if (data.ageTo) {
      const from = parseInt(data.ageFrom, 10);
      const to = parseInt(data.ageTo, 10);
      if (!isNaN(from) && to <= from) {
        ctx.addIssue({ code: 'custom', path: ['ageTo'], message: 'Must be greater than From' });
      }
    }
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

const inputClass =
  'bg-white rounded-xl border-[1.5px] border-separator px-4 py-[14px] text-base text-fg';

function LookingForScreenInner() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const [religionSheetOpen, setReligionSheetOpen] = useState(false);

  const { control, getValues, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    mode: 'onChange',
    defaultValues: {
      interestedGender: datingProfile?.interestedGender ?? [],
      ageFrom: String(datingProfile?.ageFrom ?? 18),
      ageTo: datingProfile?.ageTo ? String(datingProfile.ageTo) : '',
      religion: datingProfile?.religion ?? RELIGIONS[0],
      religiousPref: (datingProfile?.religiousPreference as Religion | null) ?? null,
    },
  });

  const patch = async (updates: Parameters<typeof patchApiDatingProfilesMe>[0]) => {
    try {
      await patchApiDatingProfilesMe(updates);
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch {
      toast.error('Could not save. Try again.');
    }
  };

  const saveAges = () => {
    const vals = getValues();
    if (!formState.errors.ageFrom && !formState.errors.ageTo) {
      const from = parseInt(vals.ageFrom, 10);
      const to = vals.ageTo ? parseInt(vals.ageTo, 10) : null;
      if (!isNaN(from)) {
        patch({ ageFrom: from, ageTo: to });
      }
    }
  };

  if (!datingProfile) return null;

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Looking for" onBack={() => router.back()} />
      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <SectionLabel>Interested in</SectionLabel>
        <Controller
          control={control}
          name="interestedGender"
          render={({ field }) => (
            <View className="flex-row flex-wrap" style={{ gap: 8 }}>
              {GENDERS.map((g) => {
                const active = field.value.includes(g);
                return (
                  <Pressable
                    key={g}
                    onPress={() => {
                      const next = active
                        ? field.value.filter((v) => v !== g)
                        : [...field.value, g];
                      field.onChange(next);
                      patch({ interestedGender: next });
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
                      {g}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          )}
        />

        <SectionLabel>Age range</SectionLabel>
        <View className="flex-row items-start" style={{ gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Text className="text-xs text-fg-muted mb-1.5">From</Text>
            <Controller
              control={control}
              name="ageFrom"
              render={({ field, fieldState }) => (
                <TextInput
                  className={cn(inputClass, fieldState.error && 'border-error')}
                  value={field.value}
                  onChangeText={field.onChange}
                  onBlur={saveAges}
                  keyboardType="number-pad"
                  maxLength={2}
                />
              )}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Text className="text-xs text-fg-muted mb-1.5">To (optional)</Text>
            <Controller
              control={control}
              name="ageTo"
              render={({ field, fieldState }) => (
                <TextInput
                  className={cn(inputClass, fieldState.error && 'border-error')}
                  value={field.value}
                  onChangeText={field.onChange}
                  onBlur={saveAges}
                  keyboardType="number-pad"
                  maxLength={2}
                  placeholder="—"
                />
              )}
            />
          </View>
        </View>

        <SectionLabel>My religion</SectionLabel>
        <Controller
          control={control}
          name="religion"
          render={({ field }) => (
            <View className="flex-row flex-wrap" style={{ gap: 8 }}>
              {RELIGIONS.map((r) => {
                const active = field.value === r;
                return (
                  <Pressable
                    key={r}
                    onPress={() => {
                      field.onChange(r);
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

        <SectionLabel>{"Partner's religion (optional)"}</SectionLabel>
        <Controller
          control={control}
          name="religiousPref"
          render={({ field }) => {
            const selected = RELIGIOUS_PREFS.find((o) => o.value === field.value);
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
                <Modal
                  visible={religionSheetOpen}
                  transparent
                  animationType="slide"
                  onRequestClose={() => setReligionSheetOpen(false)}
                >
                  <View
                    style={{
                      flex: 1,
                      justifyContent: 'flex-end',
                      backgroundColor: 'rgba(0,0,0,0.3)',
                    }}
                  >
                    <View
                      style={{ maxHeight: '70%', backgroundColor: 'white' }}
                      className="rounded-t-[20px] pb-8"
                    >
                      <View
                        className="flex-row justify-end p-4"
                        style={{
                          borderBottomWidth: StyleSheet.hairlineWidth,
                          borderBottomColor: colors.divider,
                        }}
                      >
                        <Pressable onPress={() => setReligionSheetOpen(false)}>
                          <Text className="text-accent text-base font-semibold">Done</Text>
                        </Pressable>
                      </View>
                      <ScrollView>
                        {RELIGIOUS_PREFS.map((opt) => {
                          const active = opt.value === field.value;
                          return (
                            <Pressable
                              key={String(opt.value)}
                              onPress={() => {
                                field.onChange(opt.value);
                                patch({ religiousPreference: opt.value });
                                setReligionSheetOpen(false);
                              }}
                              className={cn(
                                'px-5 py-4 flex-row items-center',
                                active && 'bg-accent-muted'
                              )}
                            >
                              <Text
                                className={cn(
                                  'text-base text-fg',
                                  active && 'text-accent font-semibold'
                                )}
                              >
                                {opt.label}
                              </Text>
                            </Pressable>
                          );
                        })}
                      </ScrollView>
                    </View>
                  </View>
                </Modal>
              </>
            );
          }}
        />
      </ScrollView>
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
