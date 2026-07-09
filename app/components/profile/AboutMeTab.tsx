import { Platform } from 'react-native';
import { ScrollView, Text, View } from '@/lib/tw';
import { useNavigation } from '@react-navigation/native';
import type { OwnDatingProfile } from '@/lib/api/generated/model';

import { Pill } from '@/components/ui/Pill';
import { Sprout } from '@/components/ui/Sprout';
import { FieldLabel } from '@/components/ui/FieldLabel';

interface Props {
  data: OwnDatingProfile;
}

// AboutMeTab keeps a tighter, monospace label look distinct from the canonical
// FieldLabel default — preserved via the style override.
const labelStyle = {
  fontSize: 10,
  letterSpacing: 1.2,
  fontWeight: '500' as const,
  fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  marginBottom: 6,
};

export function AboutMeTab({ data }: Props) {
  const navigation = useNavigation();

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
      {/* Bio */}
      {data.bio ? (
        <View>
          <FieldLabel style={labelStyle}>Bio</FieldLabel>
          <Text className="text-ink-mid" style={{ fontSize: 14.5, lineHeight: 22 }}>
            {data.bio}
          </Text>
        </View>
      ) : null}

      {/* Looking for / Age range */}
      <View style={{ flexDirection: 'row', gap: 12 }}>
        <View style={{ flex: 1 }}>
          <FieldLabel style={labelStyle}>Looking for</FieldLabel>
          <Pill tone="leaf">{lookingFor}</Pill>
        </View>
        <View style={{ flex: 1 }}>
          <FieldLabel style={labelStyle}>Age range</FieldLabel>
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '500' }}>
            {ageText}
          </Text>
        </View>
      </View>

      {/* City / Religion */}
      <View style={{ flexDirection: 'row', gap: 12 }}>
        <View style={{ flex: 1 }}>
          <FieldLabel style={labelStyle}>City</FieldLabel>
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '500' }}>
            {data.city}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <FieldLabel style={labelStyle}>Religion</FieldLabel>
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '500' }}>
            {data.religion}
          </Text>
        </View>
      </View>

      {/* Interests */}
      {data.interests.length > 0 ? (
        <View>
          <FieldLabel style={labelStyle}>Interests</FieldLabel>
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
        <Sprout block variant="secondary" onPress={() => navigation.navigate('ProfileEdit')}>
          Edit Profile
        </Sprout>
      </View>
    </ScrollView>
  );
}
