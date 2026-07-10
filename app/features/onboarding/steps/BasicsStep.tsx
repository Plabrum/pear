import { useState } from 'react';
import { Pressable, ScrollView, TextInput, View } from '@/lib/tw';
import { cn } from '@/lib/cn';
import DateInput from '@/components/DateInput';
import { Pill } from '@/components/Pill';
import { createTypedForm } from '@/lib/forms/typed-form';
import { GENDERS, CITIES } from '@/constants/enums';
import { colors } from '@/constants/theme';
import { updateMyProfile, createDatingProfile, switchToWinger } from '@/lib/api/actions';
import { useAuth } from '@/context/auth';
import type { UserRole, Gender as GenderModel, City } from '@/lib/api/generated/model';
import { ChipRow, MonoLabel, StepHeader } from '@/features/onboarding/chrome';

type Role = UserRole;
type Gender = GenderModel;

const PRONOUNS = ['she/her', 'he/him', 'they/them'] as const;

type BasicsValues = {
  chosenName: string;
  dateOfBirth: Date;
  gender: Gender;
  interestedGender: Gender[];
  city: City;
};
const basicsForm = createTypedForm<BasicsValues>();

// Multi-select chip row — onboarding's "interested in" allows multiple genders.
function MultiChipRow({
  options,
  value,
  onChange,
}: {
  options: readonly Gender[];
  value: Gender[];
  onChange: (v: Gender[]) => void;
}) {
  return (
    <View className="flex-row flex-wrap" style={{ gap: 6 }}>
      {options.map((opt) => {
        const active = value.includes(opt);
        return (
          <Pressable
            key={opt}
            onPress={() => onChange(active ? value.filter((v) => v !== opt) : [...value, opt])}
          >
            <Pill label={opt} tone={active ? 'leaf' : 'outline'} size="md" />
          </Pressable>
        );
      })}
    </View>
  );
}

export function BasicsStep({
  role,
  defaultPhoneNumber,
  onComplete,
}: {
  role: Role;
  defaultPhoneNumber: string;
  onComplete: (newDpId: string | null) => void;
}) {
  const [pronouns, setPronouns] = useState<string | null>(null);
  const { userId } = useAuth();

  return (
    <basicsForm.Form
      defaultValues={{
        chosenName: '',
        dateOfBirth: undefined,
        gender: undefined,
        interestedGender: [],
        city: undefined,
      }}
      onSubmit={async (v) => {
        // The profile already exists (created at auth); update it by its id,
        // which is the caller's userId.
        await updateMyProfile(userId, {
          chosenName: v.chosenName.trim(),
          dateOfBirth: v.dateOfBirth.toISOString().split('T')[0],
          phoneNumber: defaultPhoneNumber.trim() || null,
          gender: v.gender,
        });
        if (role !== 'dater') {
          // Role starts at DATER; a winger flips it through the transition action.
          await switchToWinger(userId);
          onComplete(null);
          return;
        }
        const dp = await createDatingProfile({
          city: v.city,
          ageFrom: 18,
          interestedGender: v.interestedGender,
          religion: 'Prefer not to say',
          interests: [],
          datingStatus: 'open',
        });
        onComplete(dp.created_id ?? null);
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
            <basicsForm.CustomField
              name="chosenName"
              requiredMessage="Enter your name"
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
            <basicsForm.CustomField
              name="dateOfBirth"
              requiredMessage="Pick a date"
              render={({ value, onChange }) => <DateInput value={value} onChange={onChange} />}
            />
          </View>
          <View>
            <MonoLabel>Pronouns</MonoLabel>
            <ChipRow options={PRONOUNS} value={pronouns} onChange={setPronouns} />
          </View>
          <View>
            <MonoLabel>Gender</MonoLabel>
            <basicsForm.CustomField
              name="gender"
              requiredMessage="Pick one"
              render={({ value, onChange }) => (
                <ChipRow
                  options={GENDERS}
                  value={(value as Gender) ?? null}
                  onChange={(g) => onChange(g)}
                />
              )}
            />
          </View>
          <View>
            <MonoLabel>Interested in</MonoLabel>
            <basicsForm.CustomField
              name="interestedGender"
              rules={{ validate: (v: Gender[]) => v.length > 0 || 'Pick at least one' }}
              render={({ value, onChange }) => (
                <MultiChipRow
                  options={GENDERS}
                  value={(value as Gender[]) ?? []}
                  onChange={onChange}
                />
              )}
            />
          </View>
          {role === 'dater' && (
            <View>
              <MonoLabel>City</MonoLabel>
              <basicsForm.CustomField
                name="city"
                requiredMessage="Pick a city"
                render={({ value, onChange }) => (
                  <ChipRow
                    options={CITIES}
                    value={(value as City) ?? null}
                    onChange={(c) => onChange(c)}
                  />
                )}
              />
            </View>
          )}
        </View>
      </ScrollView>
      <basicsForm.SubmitButton label="Continue" size="md" />
    </basicsForm.Form>
  );
}
