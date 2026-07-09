import { useState } from 'react';
import { KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView, View } from '@/lib/tw';
import type { UserRole } from '@/lib/api/generated/model';
import { BackButton, Progress } from '@/components/onboarding/chrome';
import { BasicsStep } from '@/components/onboarding/steps/BasicsStep';
import { PhotosStep } from '@/components/onboarding/steps/PhotosStep';
import { PromptsStep } from '@/components/onboarding/steps/PromptsStep';
import { WingInviteStep } from '@/components/onboarding/steps/WingInviteStep';

type Role = UserRole;
type Step = 1 | 2 | 3 | 4;

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
    setStep((s) => Math.min(4, s + 1) as Step);
  }

  function goBack() {
    if (step === 1) {
      onBackToRole();
      return;
    }
    setStep((s) => Math.max(1, s - 1) as Step);
  }

  function renderStep() {
    switch (step) {
      case 1:
        return (
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
        );
      case 2:
        return <PhotosStep dpId={dpId} onContinue={goNext} />;
      case 3:
        return <PromptsStep onContinue={goNext} />;
      case 4:
        return <WingInviteStep onFinish={onFinish} />;
    }
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
            {renderStep()}
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
