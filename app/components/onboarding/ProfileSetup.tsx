import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Share } from 'react-native';
import PulseSpinner from '@/components/ui/PulseSpinner';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { z } from 'zod';
import { Pressable, SafeAreaView, ScrollView, Text, TextInput, View } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { Sprout } from '@/components/ui/Sprout';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { PearMark } from '@/components/ui/PearMark';
import DateInput from '@/components/ui/DateInput';
import { createForm, RootError, useFormSubmit } from '@/lib/forms';
import { GENDERS } from '@/constants/enums';
import { colors } from '@/constants/theme';
import {
  patchApiProfilesMe,
  postApiDatingProfiles,
  getApiDatingProfilesMe,
} from '@/lib/api/generated/profiles/profiles';
import {
  postApiProfilePrompts,
  useGetApiPromptTemplatesOnboardingSuspense,
} from '@/lib/api/generated/prompts/prompts';
import { postApiPhotosIdReject } from '@/lib/api/generated/photos/photos';
import { useUploadProfilePhoto } from '@/hooks/use-upload-profile-photo';
import { getPhotoUrl, pickAndResizePhoto } from '@/lib/photos';
import type { Database } from '@/types/database';
import { toast } from 'sonner-native';

type Role = Database['public']['Enums']['user_role'];
type Gender = Database['public']['Enums']['gender'];

type Step = 1 | 2 | 3 | 4;

const PRONOUNS = ['she/her', 'he/him', 'they/them'] as const;

type Props = {
  role: Role;
  defaultPhoneNumber: string;
  initialDpId: string | null;
  onDpCreated: (id: string) => void;
  onFinish: () => void;
  onBackToRole: () => void;
};

export default function ProfileSetup({
  role,
  defaultPhoneNumber,
  initialDpId,
  onDpCreated,
  onFinish,
  onBackToRole,
}: Props) {
  const [step, setStep] = useState<Step>(1);
  const [dpId, setDpId] = useState<string | null>(initialDpId);

  const lastStep: Step = role === 'dater' ? 4 : 1;

  function goNext() {
    if (step === lastStep) {
      onFinish();
      return;
    }
    setStep((s) => Math.min(4, (s + 1) as Step) as Step);
  }

  function goBack() {
    if (step === 1) {
      onBackToRole();
      return;
    }
    setStep((s) => Math.max(1, s - 1) as Step);
  }

  return (
    <SafeAreaView className="flex-1 bg-background">
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View className="flex-1 px-6 pt-16 pb-7">
          <BackButton onPress={goBack} />
          <View className="flex-1">
            <Progress step={step} />
            {step === 1 ? (
              <BasicsStep
                role={role}
                defaultPhoneNumber={defaultPhoneNumber}
                onComplete={(newDpId) => {
                  if (newDpId) {
                    setDpId(newDpId);
                    onDpCreated(newDpId);
                  }
                  goNext();
                }}
              />
            ) : null}
            {step === 2 ? <PhotosStep dpId={dpId} onContinue={goNext} /> : null}
            {step === 3 ? <PromptsStep onContinue={goNext} /> : null}
            {step === 4 ? <WingInviteStep onFinish={onFinish} /> : null}
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ── Shared chrome ───────────────────────────────────────────────────

function BackButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} className="self-start mb-3.5 flex-row items-center" hitSlop={8}>
      <Text className="text-foreground-muted" style={{ fontSize: 18, marginRight: 4 }}>
        ‹
      </Text>
      <Text className="text-[13px] text-foreground-muted font-medium">Back</Text>
    </Pressable>
  );
}

function Progress({ step }: { step: Step }) {
  return (
    <View className="flex-row items-center mb-[18px]" style={{ gap: 6 }}>
      {[1, 2, 3, 4].map((s) => (
        <View
          key={s}
          className={cn('flex-1 rounded-[2px]', s <= step ? 'bg-primary' : 'bg-border')}
          style={{ height: 3 }}
        />
      ))}
    </View>
  );
}

function StepHeader({
  kicker,
  title,
  accent,
  sub,
}: {
  kicker: string;
  title: string;
  accent?: string;
  sub?: string;
}) {
  return (
    <>
      <Text
        className="font-mono text-foreground-subtle uppercase mb-2.5"
        style={{ fontSize: 10.5, letterSpacing: 1.6 }}
      >
        {kicker}
      </Text>
      <Text
        className="font-serif text-foreground"
        style={{ fontSize: 28, lineHeight: 30, letterSpacing: -0.7 }}
      >
        {title}
        {accent ? (
          <Text
            className="font-serif text-primary"
            style={{ fontSize: 28, lineHeight: 30, letterSpacing: -0.7, fontStyle: 'italic' }}
          >
            {' '}
            {accent}
          </Text>
        ) : null}
        .
      </Text>
      {sub ? (
        <Text className="text-sm text-foreground-muted mt-2.5 leading-[21px]">{sub}</Text>
      ) : null}
    </>
  );
}

function MonoLabel({ children }: { children: React.ReactNode }) {
  return (
    <Text
      className="font-mono text-foreground-subtle uppercase mb-1.5"
      style={{ fontSize: 10.5, letterSpacing: 1.4 }}
    >
      {children}
    </Text>
  );
}

function ChipRow<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly T[];
  value: T | null;
  onChange: (v: T) => void;
}) {
  return (
    <View className="flex-row flex-wrap" style={{ gap: 6 }}>
      {options.map((opt) => {
        const active = value === opt;
        return (
          <Pressable
            key={opt}
            onPress={() => onChange(opt)}
            className={cn(
              'h-[30px] px-3 rounded-full items-center justify-center border',
              active ? 'bg-primary-soft border-transparent' : 'bg-transparent border-border'
            )}
          >
            <Text
              className={cn(
                'text-[12.5px] font-medium',
                active ? 'text-primary' : 'text-foreground-muted'
              )}
            >
              {opt}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// ── Step 1 — basics ────────────────────────────────────────────────

const basicsSchema = z.object({
  chosenName: z.string().min(1, 'Enter your name'),
  dateOfBirth: z.date({ message: 'Pick a date' }),
  gender: z.enum(GENDERS),
});
const basicsForm = createForm(basicsSchema);

function BasicsStep({
  role,
  defaultPhoneNumber,
  onComplete,
}: {
  role: Role;
  defaultPhoneNumber: string;
  onComplete: (newDpId: string | null) => void;
}) {
  const [pronouns, setPronouns] = useState<string | null>(null);

  return (
    <basicsForm.Form
      defaultValues={{ chosenName: '', dateOfBirth: undefined, gender: undefined }}
      onSubmit={async (v) => {
        await patchApiProfilesMe({
          chosenName: v.chosenName.trim(),
          dateOfBirth: v.dateOfBirth.toISOString().split('T')[0],
          phoneNumber: defaultPhoneNumber.trim() || null,
          gender: v.gender,
          role,
        });
        if (role !== 'dater') {
          onComplete(null);
          return;
        }
        const dp = await postApiDatingProfiles({
          city: 'Boston',
          ageFrom: 18,
          interestedGender: [],
          religion: 'Prefer not to say',
          interests: [],
          datingStatus: 'open',
        });
        onComplete(dp.id);
      }}
    >
      <ScrollView
        className="flex-1"
        contentContainerClassName="pb-4"
        keyboardShouldPersistTaps="handled"
      >
        <StepHeader
          kicker="Step 1 · The basics"
          title="Tell us about"
          accent="yourself"
          sub="Just the basics first."
        />
        <View className="mt-[22px]" style={{ gap: 14 }}>
          <View>
            <MonoLabel>First name</MonoLabel>
            <basicsForm.Field
              name="chosenName"
              render={({ value, onChange, invalid }) => (
                <TextInput
                  value={value ?? ''}
                  onChangeText={onChange}
                  autoCapitalize="words"
                  placeholder="Your first name"
                  placeholderTextColor={colors.inkGhost}
                  className={cn(
                    'bg-surface rounded-[14px] border-[1.5px] px-4 py-[14px] font-serif text-foreground',
                    invalid ? 'border-destructive' : 'border-primary'
                  )}
                  style={{ fontSize: 22 }}
                />
              )}
            />
          </View>
          <View>
            <MonoLabel>Birthday</MonoLabel>
            <basicsForm.Field
              name="dateOfBirth"
              render={({ value, onChange }) => <DateInput value={value} onChange={onChange} />}
            />
          </View>
          <View>
            <MonoLabel>Pronouns</MonoLabel>
            <ChipRow options={PRONOUNS} value={pronouns} onChange={setPronouns} />
          </View>
          <View>
            <MonoLabel>Gender</MonoLabel>
            <basicsForm.Field
              name="gender"
              render={({ value, onChange }) => (
                <ChipRow
                  options={GENDERS}
                  value={(value as Gender) ?? null}
                  onChange={(g) => onChange(g)}
                />
              )}
            />
          </View>
        </View>
        <RootError />
      </ScrollView>
      <BasicsCta />
    </basicsForm.Form>
  );
}

function BasicsCta() {
  const { submit, isValid, isSubmitting } = useFormSubmit();
  return (
    <Sprout block size="md" onPress={submit} disabled={!isValid} loading={isSubmitting}>
      Continue
    </Sprout>
  );
}

// ── Step 2 — photos ────────────────────────────────────────────────

type LocalPhoto = { id: string; uri: string };

function PhotosStep({ dpId, onContinue }: { dpId: string | null; onContinue: () => void }) {
  const [photos, setPhotos] = useState<LocalPhoto[]>([]);
  const { upload, isPending: uploading } = useUploadProfilePhoto();

  async function refresh() {
    const data = await getApiDatingProfilesMe();
    if (!data) return;
    setPhotos(
      data.photos.flatMap((p) => {
        const uri = getPhotoUrl(p.storageUrl);
        return uri ? [{ id: p.id, uri }] : [];
      })
    );
  }

  async function handleAdd() {
    if (!dpId || photos.length >= 6) return;
    const uri = await pickAndResizePhoto();
    if (!uri) return;
    const ok = await upload(dpId, uri, `${Date.now()}.jpg`, photos.length);
    if (ok) await refresh();
  }

  async function handleRemove(photoId: string) {
    const previous = photos;
    setPhotos((p) => p.filter((x) => x.id !== photoId));
    try {
      await postApiPhotosIdReject(photoId);
    } catch {
      setPhotos(previous);
      toast.error('Failed to remove photo. Please try again.');
    }
  }

  const slots = Array.from({ length: 6 }, (_, i) => photos[i] ?? null);
  const canContinue = photos.length >= 1;

  return (
    <View className="flex-1">
      <ScrollView className="flex-1" contentContainerClassName="pb-4">
        <StepHeader
          kicker="Step 2 · Show up"
          title="Add a few"
          accent="photos"
          sub="At least one. The first one shows up biggest."
        />
        <View className="flex-row flex-wrap mt-[22px]" style={{ gap: 8 }}>
          {slots.map((slot, i) => (
            <View key={i} style={{ width: '31%', aspectRatio: 3 / 4 }}>
              {slot ? (
                <PhotoSlot photo={slot} isMain={i === 0} onRemove={() => handleRemove(slot.id)} />
              ) : (
                <EmptySlot onPress={handleAdd} disabled={uploading || !dpId} />
              )}
            </View>
          ))}
        </View>
        <View
          className="mt-4 px-3.5 py-3 rounded-[14px] bg-primary-soft flex-row items-start"
          style={{ gap: 10 }}
        >
          <View
            className="w-7 h-7 rounded-full bg-primary items-center justify-center"
            style={{ flexShrink: 0 }}
          >
            <PearMark size={16} color="#FBF8F1" leaf="#FBF8F1" stem="#FBF8F1" variant="flat" />
          </View>
          <Text className="flex-1 text-[12.5px] text-foreground-muted leading-[18px]">
            <Text className="text-foreground font-semibold">Ask a wingperson</Text> to suggest a
            photo of you they think shows up well.
          </Text>
        </View>
      </ScrollView>
      <Sprout block size="md" onPress={onContinue} disabled={!canContinue}>
        Continue
      </Sprout>
    </View>
  );
}

function PhotoSlot({
  photo,
  isMain,
  onRemove,
}: {
  photo: LocalPhoto;
  isMain: boolean;
  onRemove: () => void;
}) {
  return (
    <View
      className={cn(
        'w-full h-full rounded-[14px] overflow-hidden relative',
        isMain ? 'border-[1.5px] border-primary' : 'border border-border'
      )}
    >
      <Image
        source={{ uri: photo.uri }}
        style={{ width: '100%', height: '100%' }}
        contentFit="cover"
      />
      {isMain ? (
        <View
          className="absolute top-1.5 left-1.5 bg-primary rounded-md"
          style={{ paddingHorizontal: 7, paddingVertical: 3 }}
        >
          <Text
            className="font-mono text-primary-foreground uppercase"
            style={{ fontSize: 10, fontWeight: '700', letterSpacing: 0.6 }}
          >
            Main
          </Text>
        </View>
      ) : null}
      <Pressable
        onPress={onRemove}
        hitSlop={6}
        className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full items-center justify-center"
        style={{ backgroundColor: 'rgba(0,0,0,0.65)' }}
      >
        <Text className="text-white text-xs font-bold">✕</Text>
      </Pressable>
    </View>
  );
}

function EmptySlot({ onPress, disabled }: { onPress: () => void; disabled: boolean }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      className={cn(
        'w-full h-full rounded-[14px] bg-surface border-[1.5px] border-dashed border-border items-center justify-center',
        disabled && 'opacity-40'
      )}
    >
      {disabled ? (
        <PulseSpinner color={colors.primary} />
      ) : (
        <Text className="text-foreground-subtle" style={{ fontSize: 24, lineHeight: 24 }}>
          +
        </Text>
      )}
    </Pressable>
  );
}

// ── Step 3 — prompts ───────────────────────────────────────────────

type AddedPrompt = { id: string; question: string; answer: string };

function PromptsStep({ onContinue }: { onContinue: () => void }) {
  const { data: templates } = useGetApiPromptTemplatesOnboardingSuspense();
  const [added, setAdded] = useState<AddedPrompt[]>([]);
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const remainingTemplates = templates.filter((t) => !added.some((a) => a.id === t.id));
  const activeTemplate = templates.find((t) => t.id === activeTemplateId) ?? null;

  async function saveAnswer() {
    const trimmed = draft.trim();
    if (!activeTemplate || !trimmed) return;
    setSubmitting(true);
    try {
      await postApiProfilePrompts({ promptTemplateId: activeTemplate.id, answer: trimmed });
      setAdded((prev) => [
        ...prev,
        { id: activeTemplate.id, question: activeTemplate.question, answer: trimmed },
      ]);
      setActiveTemplateId(null);
      setDraft('');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save prompt');
    } finally {
      setSubmitting(false);
    }
  }

  const slots = Array.from({ length: 3 }, (_, i) => added[i] ?? null);
  const canContinue = added.length >= 1;

  return (
    <View className="flex-1">
      <ScrollView
        className="flex-1"
        contentContainerClassName="pb-4"
        keyboardShouldPersistTaps="handled"
      >
        <StepHeader
          kicker="Step 3 · Sound like you"
          title="Pick"
          accent="three prompts"
          sub="The good ones reveal something specific. Skip the bumper-sticker answers."
        />
        <View className="mt-5" style={{ gap: 10 }}>
          {slots.map((slot, i) => (
            <View
              key={i}
              className={cn(
                'bg-surface rounded-2xl px-3.5 py-3 border',
                slot ? 'border-primary/30' : 'border-border'
              )}
              style={{ gap: 4 }}
            >
              <View className="flex-row items-center justify-between">
                <Text
                  className="font-mono text-foreground-subtle uppercase"
                  style={{ fontSize: 10, letterSpacing: 1.4 }}
                >
                  {slot ? slot.question : `Prompt ${i + 1}`}
                </Text>
                {slot ? (
                  <Text className="text-primary" style={{ fontSize: 14 }}>
                    ✓
                  </Text>
                ) : null}
              </View>
              <Text
                className={cn(
                  'font-serif',
                  slot ? 'text-foreground' : 'text-foreground-subtle italic'
                )}
                style={{ fontSize: 16, lineHeight: 21 }}
              >
                {slot ? `"${slot.answer}"` : 'Tap to answer'}
              </Text>
            </View>
          ))}
          <Pressable
            onPress={() => {
              const next = remainingTemplates[0];
              if (next) setActiveTemplateId(next.id);
            }}
            disabled={remainingTemplates.length === 0 || added.length >= 3}
            className={cn(
              'rounded-2xl border-[1.5px] border-dashed border-border py-3.5 flex-row items-center justify-center',
              (remainingTemplates.length === 0 || added.length >= 3) && 'opacity-40'
            )}
          >
            <Text className="text-foreground-muted text-[13.5px] font-semibold">
              + Browse all prompts
            </Text>
          </Pressable>
        </View>

        {activeTemplate ? (
          <View className="mt-4 bg-surface rounded-2xl border border-border p-4">
            <Text className="text-sm text-foreground-muted mb-2">{activeTemplate.question}</Text>
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Your answer..."
              placeholderTextColor={colors.inkGhost}
              multiline
              autoFocus
              className="min-h-20 bg-background rounded-xl border border-border px-3.5 py-3 text-base text-foreground"
              style={{ textAlignVertical: 'top' }}
            />
            <View className="flex-row mt-3" style={{ gap: 8 }}>
              <Sprout
                size="sm"
                variant="secondary"
                onPress={() => {
                  setActiveTemplateId(null);
                  setDraft('');
                }}
              >
                Cancel
              </Sprout>
              <Sprout size="sm" onPress={saveAnswer} disabled={!draft.trim()} loading={submitting}>
                Save
              </Sprout>
            </View>
          </View>
        ) : null}
      </ScrollView>
      <Sprout block size="md" onPress={onContinue} disabled={!canContinue}>
        Continue
      </Sprout>
    </View>
  );
}

// ── Step 4 — wing invite ───────────────────────────────────────────

function WingInviteStep({ onFinish }: { onFinish: () => void }) {
  async function shareLink() {
    try {
      await Share.share({
        message: 'Be my wingperson on Pear: https://pearwingmate.app/invite',
      });
    } catch {
      // user cancelled
    }
  }

  function fromContacts() {
    onFinish();
    router.replace('/(tabs)/profile/wingpeople' as any);
  }

  return (
    <View className="flex-1">
      <ScrollView className="flex-1" contentContainerClassName="pb-4">
        <StepHeader
          kicker="Step 4 · Bring a friend"
          title="Invite a"
          accent="wingperson"
          sub="They'll see profiles you swipe on, and can hand-pick people for you."
        />
        <View className="mt-5 p-[18px] bg-surface rounded-[20px] border border-border">
          <View className="flex-row items-center justify-center mb-3.5" style={{ paddingLeft: 14 }}>
            <View>
              <FaceAvatar name="Priya" size={52} ring={2} />
            </View>
            <View style={{ marginLeft: -14 }}>
              <FaceAvatar name="Jordan" size={52} ring={2} />
            </View>
            <View style={{ marginLeft: -14 }}>
              <FaceAvatar name="Sasha" size={52} ring={2} />
            </View>
          </View>
          <Text className="text-[13px] text-foreground-muted text-center leading-[19px] mb-3">
            Pick people who <Text className="text-foreground font-semibold">actually know you</Text>
            . Quality {'>'} quantity.
          </Text>
          <View style={{ gap: 8 }}>
            <Sprout block size="md" onPress={fromContacts}>
              From contacts
            </Sprout>
            <Sprout block size="md" variant="secondary" onPress={shareLink}>
              Share a link
            </Sprout>
          </View>
        </View>
        <Text className="mt-3.5 text-xs text-foreground-subtle text-center leading-[18px]">
          You can do this later. Pear works either way.
        </Text>
      </ScrollView>
      <Sprout block size="md" onPress={onFinish}>
        Finish setup
      </Sprout>
    </View>
  );
}
