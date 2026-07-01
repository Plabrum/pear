import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import {
  useGetApiDatingProfilesMeSuspense,
  useGetApiProfilesMeSuspense,
} from '@/lib/api/generated/profiles/profiles';
import type { OwnDatingProfileResponse } from '@/lib/api/generated/model';
import { View, Text, ScrollView, SafeAreaView, Pressable } from '@/lib/tw';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import ScreenSuspense from '@/components/ui/ScreenSuspense';

const INK = '#1F1B16';
const LEAF = '#5A8C3A';
const LINE = 'rgba(31,27,22,0.10)';

// ── Ripeness helpers ──────────────────────────────────────────────────────────

function ripenessLabel(score: number): string {
  if (score >= 100) return 'Fully ripe';
  if (score >= 85) return 'Almost ripe';
  if (score >= 60) return 'Getting there';
  if (score >= 40) return 'Taking shape';
  return 'Just sprouting';
}

function ripenessHint(data: NonNullable<OwnDatingProfileResponse>): string | null {
  const approvedPhotos = data.photos.filter((p) => p.approvedAt !== null);
  if (data.prompts.length < 3) return 'Add one more prompt to ripen';
  if (approvedPhotos.length < 6) return 'Add more photos';
  if (!data.bio) return 'Add a bio';
  if (data.interests.length === 0) return 'Add some interests';
  return null;
}

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
        color: 'rgba(31,27,22,0.45)',
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
        borderColor: LINE,
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
              color: subAccent ? '#C0392B' : 'rgba(31,27,22,0.50)',
            }}
            numberOfLines={1}
          >
            {sub}
          </Text>
        ) : null}
      </View>
      <Ionicons name="chevron-forward" size={16} color="rgba(31,27,22,0.35)" />
    </Pressable>
  );
}

function RipenessBar({ data }: { data: NonNullable<OwnDatingProfileResponse> }) {
  const score = data.ripeness;
  const label = ripenessLabel(score);
  const hint = ripenessHint(data);

  return (
    <View
      className="bg-surface"
      style={{
        borderRadius: 18,
        borderWidth: 1,
        borderColor: LINE,
        padding: 16,
        marginBottom: 4,
      }}
    >
      <View className="flex-row items-center" style={{ gap: 8, marginBottom: 10 }}>
        <Text style={{ fontSize: 26 }}>🍐</Text>
        <View style={{ flex: 1 }}>
          <Text className="text-fg" style={{ fontSize: 16, fontWeight: '700' }}>
            {label}
          </Text>
          {hint ? (
            <Text style={{ fontSize: 12.5, color: 'rgba(31,27,22,0.55)', marginTop: 1 }}>
              {hint}
            </Text>
          ) : null}
        </View>
        <View
          className="bg-primary-soft"
          style={{ borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4 }}
        >
          <Text style={{ fontSize: 12, fontWeight: '700', color: LEAF }}>{score}% ripe</Text>
        </View>
      </View>
      <View className="bg-surface-muted" style={{ height: 6, borderRadius: 3, overflow: 'hidden' }}>
        <View
          style={{
            height: 6,
            borderRadius: 3,
            backgroundColor: LEAF,
            width: `${score}%`,
          }}
        />
      </View>
    </View>
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
    isApproved: boolean;
    author: { id: string; chosenName: string | null; avatarUrl: string | null } | null;
  };
}) {
  return (
    <View
      className="bg-surface"
      style={{
        borderRadius: 14,
        borderWidth: 1,
        borderColor: LINE,
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
          style={{ fontSize: 11, color: 'rgba(31,27,22,0.45)', marginBottom: 2, fontWeight: '500' }}
        >
          {promptQuestion}
        </Text>
        <Text className="text-fg" style={{ fontSize: 13.5, lineHeight: 19 }}>
          {response.message}
        </Text>
        {!response.isApproved ? (
          <Text style={{ fontSize: 11, color: LEAF, marginTop: 3, fontWeight: '600' }}>
            Pending approval
          </Text>
        ) : null}
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

function EditProfileHub() {
  const router = useRouter();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();
  const { data: profile } = useGetApiProfilesMeSuspense();

  if (!datingProfile) {
    return (
      <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
        <View
          className="flex-row items-center"
          style={{ paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, gap: 4 }}
        >
          <Pressable
            onPress={() => router.back()}
            hitSlop={12}
            style={{ padding: 8, marginLeft: -4 }}
          >
            <Ionicons name="chevron-back" size={22} color={INK} />
          </Pressable>
          <Text
            className="font-serif text-fg"
            style={{ fontSize: 26, letterSpacing: -0.4, flex: 1 }}
          >
            Edit profile
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  const name = profile?.chosenName ?? null;
  const age = profile?.dateOfBirth ? computeAge(profile.dateOfBirth) : null;
  const approvedPhotos = datingProfile.photos.filter((p) => p.approvedAt !== null);
  const suggestedPending = datingProfile.photos.filter(
    (p) => p.suggesterId !== null && p.approvedAt === null
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
      <View
        className="flex-row items-center"
        style={{ paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, gap: 4 }}
      >
        <Pressable
          onPress={() => router.back()}
          hitSlop={12}
          style={{ padding: 8, marginLeft: -4 }}
        >
          <Ionicons name="chevron-back" size={22} color={INK} />
        </Pressable>
        <Text className="font-serif text-fg" style={{ fontSize: 26, letterSpacing: -0.4, flex: 1 }}>
          Edit profile
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 48 }}
        showsVerticalScrollIndicator={false}
      >
        <RipenessBar data={datingProfile} />

        <SectionHeader label="Photos & Basics" />
        <MenuRow
          title="Photos"
          sub={photoSub}
          onPress={() => router.push('/(tabs)/profile/edit/photos' as any)}
        />
        <MenuRow
          title="Name & basics"
          sub={nameSub || undefined}
          onPress={() => router.push('/(tabs)/profile/edit/basics' as any)}
        />
        <MenuRow
          title="Looking for"
          sub={lookingForSub || undefined}
          onPress={() => router.push('/(tabs)/profile/edit/looking-for' as any)}
        />

        <SectionHeader label="Sound Like You" />
        <MenuRow
          title="Prompts"
          sub={promptsSub}
          subAccent={promptsAccent}
          onPress={() => router.push('/(tabs)/profile/edit/prompts' as any)}
        />
        <MenuRow
          title="Bio"
          sub={bioSub}
          onPress={() => router.push('/(tabs)/profile/edit/bio' as any)}
        />
        <MenuRow
          title="Interests"
          sub={interestsSub}
          onPress={() => router.push('/(tabs)/profile/edit/interests' as any)}
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
