import { useNavigation } from '@react-navigation/native';
import Ionicons from 'react-native-vector-icons/Ionicons';

import {
  useGetApiDatingProfilesMeSuspense,
  useGetApiProfilesMeSuspense,
} from '@/lib/api/generated/profiles/profiles';
import { View, Text, ScrollView, SafeAreaView, Pressable } from '@/lib/tw';
import { FaceAvatar } from '@/components/FaceAvatar';
import { colors } from '@/constants/theme';
import ScreenSuspense from '@/components/ScreenSuspense';
import { LargeNavHeader } from '@/components/LargeNavHeader';

// ── Local components ──────────────────────────────────────────────────────────

function SectionHeader({ label }: { label: string }) {
  return (
    <Text
      style={{
        fontSize: 10,
        letterSpacing: 1.2,
        textTransform: 'uppercase',
        fontWeight: '500',
        fontFamily: 'Menlo',
        color: colors.inkAlpha45,
        marginTop: 28,
        marginBottom: 8,
      }}
    >
      {label}
    </Text>
  );
}

function MenuRow({
  icon,
  title,
  sub,
  subAccent,
  onPress,
}: {
  icon?: React.ReactNode;
  title: string;
  sub?: string;
  subAccent?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      className="bg-surface flex-row items-center"
      style={{
        borderRadius: 14,
        borderWidth: 1,
        borderColor: colors.divider,
        paddingHorizontal: 14,
        paddingVertical: 12,
        gap: 12,
        marginBottom: 8,
      }}
    >
      {icon ? (
        <View
          className="bg-surface-muted items-center justify-center"
          style={{ width: 36, height: 36, borderRadius: 10 }}
        >
          {icon}
        </View>
      ) : null}
      <View style={{ flex: 1 }}>
        <Text className="text-fg" style={{ fontSize: 15, fontWeight: '600' }}>
          {title}
        </Text>
        {sub ? (
          <Text
            style={{
              fontSize: 12.5,
              marginTop: 1,
              color: subAccent ? colors.passRed : colors.inkAlpha50,
            }}
            numberOfLines={1}
          >
            {sub}
          </Text>
        ) : null}
      </View>
      <Ionicons name="chevron-forward" size={16} color={colors.inkAlpha35} />
    </Pressable>
  );
}

// ── Screen helpers ────────────────────────────────────────────────────────────

function computeAge(dob: string): number | null {
  const d = new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age;
}

function WingpersonResponseRow({
  promptQuestion,
  response,
}: {
  promptQuestion: string;
  response: {
    id: string;
    message: string;
    status: 'pending' | 'approved' | 'rejected';
    author: { id: string; chosenName: string | null; avatarUrl: string | null } | null;
  };
}) {
  return (
    <View
      className="bg-surface"
      style={{
        borderRadius: 14,
        borderWidth: 1,
        borderColor: colors.divider,
        padding: 12,
        marginBottom: 8,
        flexDirection: 'row',
        gap: 10,
        alignItems: 'flex-start',
      }}
    >
      <FaceAvatar
        name={response.author?.chosenName ?? ''}
        size={30}
        photoUri={response.author?.avatarUrl ?? null}
      />
      <View style={{ flex: 1 }}>
        <Text
          style={{ fontSize: 11, color: colors.inkAlpha45, marginBottom: 2, fontWeight: '500' }}
        >
          {promptQuestion}
        </Text>
        <Text className="text-fg" style={{ fontSize: 13.5, lineHeight: 19 }}>
          {response.message}
        </Text>
        {response.status !== 'approved' ? (
          <Text style={{ fontSize: 11, color: colors.leaf, marginTop: 3, fontWeight: '600' }}>
            Pending approval
          </Text>
        ) : null}
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

function EditProfileHub() {
  const navigation = useNavigation();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const { data: profile } = useGetApiProfilesMeSuspense();

  if (!datingProfile) {
    return (
      <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
        <LargeNavHeader back onBack={() => navigation.goBack()} title="Edit profile" />
      </SafeAreaView>
    );
  }

  const name = profile?.chosenName ?? null;
  const age = profile?.dateOfBirth ? computeAge(profile.dateOfBirth) : null;
  const approvedPhotos = datingProfile.photos.filter((p) => p.status === 'approved');
  const suggestedPending = datingProfile.photos.filter(
    (p) => p.suggesterId !== null && p.status === 'pending'
  );

  const photoSub = [
    `${approvedPhotos.length} of 6`,
    suggestedPending.length > 0
      ? `${suggestedPending.length} suggestion${suggestedPending.length > 1 ? 's' : ''} pending`
      : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const nameSub = [name, age != null ? String(age) : null, datingProfile.city ?? null]
    .filter(Boolean)
    .join(' · ');

  const lookingForSub = [
    datingProfile.interestedGender.join(', ') || null,
    datingProfile.ageFrom != null
      ? `${datingProfile.ageFrom}${datingProfile.ageTo ? `–${datingProfile.ageTo}` : '+'}`
      : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const promptsNeed = 3 - datingProfile.prompts.length;
  const promptsSub =
    promptsNeed > 0
      ? `${datingProfile.prompts.length} of 3 · add ${promptsNeed} more`
      : `${datingProfile.prompts.length} of 3`;
  const promptsAccent = promptsNeed > 0;

  const bioSub = datingProfile.bio
    ? datingProfile.bio.slice(0, 60) + (datingProfile.bio.length > 60 ? '…' : '')
    : 'Not set';

  const interestsSub =
    datingProfile.interests.length > 0
      ? `${datingProfile.interests.length} selected · ${datingProfile.interests.slice(0, 2).join(', ')}${datingProfile.interests.length > 2 ? ', …' : ''}`
      : 'None selected';

  const allResponses = datingProfile.prompts.flatMap((p) =>
    p.responses.map((r) => ({ promptQuestion: p.template.question, response: r }))
  );

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <LargeNavHeader back onBack={() => navigation.goBack()} title="Edit profile" />

      <ScrollView
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 48 }}
        showsVerticalScrollIndicator={false}
      >
        <SectionHeader label="Photos & Basics" />
        <MenuRow
          title="Photos"
          sub={photoSub}
          onPress={() => navigation.navigate('ProfileEditPhotos')}
        />
        <MenuRow
          title="Name & basics"
          sub={nameSub || undefined}
          onPress={() => navigation.navigate('ProfileEditBasics')}
        />
        <MenuRow
          title="Looking for"
          sub={lookingForSub || undefined}
          onPress={() => navigation.navigate('ProfileEditLookingFor')}
        />

        <SectionHeader label="Sound Like You" />
        <MenuRow
          title="Prompts"
          sub={promptsSub}
          subAccent={promptsAccent}
          onPress={() => navigation.navigate('ProfileEditPrompts')}
        />
        <MenuRow title="Bio" sub={bioSub} onPress={() => navigation.navigate('ProfileEditBio')} />
        <MenuRow
          title="Interests"
          sub={interestsSub}
          onPress={() => navigation.navigate('ProfileEditInterests')}
        />

        {allResponses.length > 0 ? (
          <>
            <SectionHeader label="Wingpeople Contributions" />
            {allResponses.map(({ promptQuestion, response }) => (
              <WingpersonResponseRow
                key={response.id}
                promptQuestion={promptQuestion}
                response={response}
              />
            ))}
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

export default function EditProfileScreen() {
  return (
    <ScreenSuspense>
      <EditProfileHub />
    </ScreenSuspense>
  );
}
