import { StyleSheet, Platform } from 'react-native';
import { ScrollView, Text, Pressable, View } from '@/lib/tw';
import { useRouter } from 'expo-router';
import { toast } from 'sonner-native';
import { useQueryClient } from '@tanstack/react-query';
import type { UseFormReturn } from 'react-hook-form';

import type { OwnDatingProfileResponse } from '@/lib/api/generated/model';
import {
  patchApiDatingProfilesMe,
  getGetApiProfilesMeQueryKey,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';

import { Pill } from '@/components/ui/Pill';
import { Sprout } from '@/components/ui/Sprout';

const INK = '#1F1B16';
const LINE = 'rgba(31,27,22,0.10)';
const LEAF = '#5A8C3A';

type DatingStatus = 'open' | 'break' | 'winging';

const STATUS_OPTIONS: { key: DatingStatus; label: string; sub: string }[] = [
  { key: 'open', label: 'Open to Dating', sub: 'Visible in Discover' },
  { key: 'break', label: 'Taking a Break', sub: 'Hidden from Discover' },
  { key: 'winging', label: 'Just Winging', sub: 'Hidden from Discover' },
];

interface Props {
  form: UseFormReturn<NonNullable<OwnDatingProfileResponse>>;
  data: NonNullable<OwnDatingProfileResponse>;
}

function FieldLabel({ children }: { children: string }) {
  return (
    <Text
      className="text-ink-dim"
      style={{
        fontSize: 10,
        letterSpacing: 1.2,
        textTransform: 'uppercase',
        fontWeight: '500',
        fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
        marginBottom: 6,
      }}
    >
      {children}
    </Text>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <View
      className="bg-surface"
      style={{
        borderRadius: 18,
        borderWidth: 1,
        borderColor: LINE,
        overflow: 'hidden',
      }}
    >
      {children}
    </View>
  );
}

export function AboutMeTab({ form, data }: Props) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const datingStatus = form.watch('datingStatus');

  const handleStatus = async (status: DatingStatus) => {
    const prev = form.getValues('datingStatus');
    form.setValue('datingStatus', status);
    try {
      await patchApiDatingProfilesMe({ datingStatus: status });
      queryClient.invalidateQueries({ queryKey: getGetApiProfilesMeQueryKey() });
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch {
      form.setValue('datingStatus', prev);
      toast.error('Could not update status. Please try again.');
    }
  };

  const ageText = data.ageTo ? `${data.ageFrom} — ${data.ageTo}` : `${data.ageFrom}+`;
  const lookingFor = data.interestedGender.length
    ? data.interestedGender.map((g) => g.toLowerCase()).join(' · ')
    : '—';

  return (
    <ScrollView
      contentContainerStyle={{ padding: 16, paddingBottom: 48, gap: 18 }}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
    >
      {/* Dating status */}
      <View>
        <FieldLabel>Dating status</FieldLabel>
        <Card>
          {STATUS_OPTIONS.map((opt, i) => {
            const active = datingStatus === opt.key;
            return (
              <Pressable
                key={opt.key}
                onPress={() => handleStatus(opt.key)}
                className="flex-row items-center"
                style={{
                  paddingHorizontal: 14,
                  paddingVertical: 12,
                  borderBottomWidth: i < STATUS_OPTIONS.length - 1 ? StyleSheet.hairlineWidth : 0,
                  borderBottomColor: LINE,
                }}
              >
                <View style={{ flex: 1 }}>
                  <Text
                    style={{
                      fontSize: 14,
                      fontWeight: '500',
                      color: active ? LEAF : INK,
                    }}
                  >
                    {opt.label}
                  </Text>
                  <Text className="text-ink-dim" style={{ fontSize: 12, marginTop: 1 }}>
                    {opt.sub}
                  </Text>
                </View>
                <View
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 10,
                    borderWidth: 2,
                    borderColor: active ? LEAF : 'rgba(31,27,22,0.20)',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {active ? (
                    <View
                      style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: LEAF }}
                    />
                  ) : null}
                </View>
              </Pressable>
            );
          })}
        </Card>
      </View>

      {datingStatus !== 'open' ? (
        <View
          className="bg-primary-soft"
          style={{
            flexDirection: 'row',
            alignItems: 'flex-start',
            gap: 8,
            borderRadius: 12,
            padding: 12,
          }}
        >
          <Text className="text-primary" style={{ flex: 1, fontSize: 13, lineHeight: 18 }}>
            Your profile is hidden from Discover while you{"'"}re{' '}
            {datingStatus === 'break' ? 'on a break' : 'just winging'}.
          </Text>
        </View>
      ) : null}

      {/* Bio */}
      {data.bio ? (
        <View>
          <FieldLabel>Bio</FieldLabel>
          <Text className="text-ink-mid" style={{ fontSize: 14.5, lineHeight: 22 }}>
            {data.bio}
          </Text>
        </View>
      ) : null}

      {/* Looking for / Age range */}
      <View style={{ flexDirection: 'row', gap: 12 }}>
        <View style={{ flex: 1 }}>
          <FieldLabel>Looking for</FieldLabel>
          <Pill tone="leaf">{lookingFor}</Pill>
        </View>
        <View style={{ flex: 1 }}>
          <FieldLabel>Age range</FieldLabel>
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '500' }}>
            {ageText}
          </Text>
        </View>
      </View>

      {/* City / Religion */}
      <View style={{ flexDirection: 'row', gap: 12 }}>
        <View style={{ flex: 1 }}>
          <FieldLabel>City</FieldLabel>
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '500' }}>
            {data.city}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <FieldLabel>Religion</FieldLabel>
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '500' }}>
            {data.religion}
          </Text>
        </View>
      </View>

      {/* Interests */}
      {data.interests.length > 0 ? (
        <View>
          <FieldLabel>Interests</FieldLabel>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {data.interests.map((interest) => (
              <Pill key={interest} tone="cream">
                {interest.toLowerCase()}
              </Pill>
            ))}
          </View>
        </View>
      ) : null}

      <View style={{ marginTop: 8 }}>
        <Sprout
          block
          variant="secondary"
          onPress={() => router.push('/(tabs)/profile/edit' as any)}
        >
          Edit Profile
        </Sprout>
      </View>
    </ScrollView>
  );
}
