import { useState } from 'react';
import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { useAuth } from '@/context/auth';
import {
  useGetApiProfilesMeSuspense,
  useGetApiDatingProfilesMeSuspense,
  getGetApiProfilesMeQueryKey,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import type { Database } from '@/types/database';
import RoleStep from '@/components/onboarding/RoleStep';
import ProfileSetup from '@/components/onboarding/ProfileSetup';

type Role = Database['public']['Enums']['user_role'];
type Step = 'role' | 'setup';

export default function OnboardingScreen() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const { data: profile } = useGetApiProfilesMeSuspense();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const initialRole = (profile?.role as Role | null) ?? null;
  const initialStep: Step = profile?.chosenName ? 'setup' : 'role';

  const [step, setStep] = useState<Step>(initialStep);
  const [role, setRole] = useState<Role | null>(initialRole);
  const [dpId, setDpId] = useState<string | null>(datingProfile?.id ?? null);

  function onRolePick(picked: Role) {
    setRole(picked);
    setStep('setup');
  }

  function invalidateAndRoute(path: string) {
    queryClient.invalidateQueries({ queryKey: getGetApiProfilesMeQueryKey() });
    queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    router.replace(path as never);
  }

  function onFinish() {
    if (role === 'winger') {
      invalidateAndRoute('/(tabs)/profile');
      return;
    }
    invalidateAndRoute('/(tabs)/discover');
  }

  switch (step) {
    case 'role':
      return <RoleStep onNext={onRolePick} />;
    case 'setup':
      return (
        <ScreenSuspense>
          <ProfileSetup
            role={role!}
            defaultPhoneNumber={session.user.phone ?? ''}
            initialDpId={dpId}
            onDpCreated={setDpId}
            onFinish={onFinish}
            onBackToRole={() => setStep('role')}
          />
        </ScreenSuspense>
      );
  }
}
