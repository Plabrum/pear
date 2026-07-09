import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { authMeQueryKey } from '@/lib/auth-session';
import { setPendingOnboardingDestination } from '@/navigation/pendingIntents';
import {
  useGetApiProfilesMeSuspense,
  useGetApiDatingProfilesMeSuspense,
  getGetApiProfilesMeQueryKey,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import type { UserRole } from '@/lib/api/generated/model';
import RoleStep from '@/components/onboarding/RoleStep';
import ProfileSetup from '@/components/onboarding/ProfileSetup';

type Role = UserRole;
type Step = 'role' | 'setup';

export default function OnboardingScreen() {
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

  function invalidateAndRoute(destination: 'Profile' | 'Discover') {
    // Mark these stale without refetching: this screen reads both via Suspense, and a
    // refetch racing the gate flip below would resolve into the unmounting screen
    // (the "state update on an unmounted component" warning). They refetch on next read.
    queryClient.invalidateQueries({
      queryKey: getGetApiProfilesMeQueryKey(),
      refetchType: 'none',
    });
    queryClient.invalidateQueries({
      queryKey: getGetApiDatingProfilesMeQueryKey(),
      refetchType: 'none',
    });
    // The routing gate reads role + hasDatingProfile off the session query, so
    // refresh it too — otherwise a just-onboarded dater is bounced back here.
    // RootNavigator's post-gate-flip effect picks this destination up once the
    // refetch above resolves and DaterTabs actually mounts.
    setPendingOnboardingDestination(destination);
    queryClient.invalidateQueries({ queryKey: authMeQueryKey });
  }

  function onFinish() {
    if (role === 'winger') {
      invalidateAndRoute('Profile');
      return;
    }
    invalidateAndRoute('Discover');
  }

  switch (step) {
    case 'role':
      return <RoleStep onNext={onRolePick} />;
    case 'setup':
      return (
        <ScreenSuspense>
          <ProfileSetup
            role={role!}
            defaultPhoneNumber=""
            initialDpId={dpId}
            onDpCreated={setDpId}
            onFinish={onFinish}
            onBackToRole={() => setStep('role')}
          />
        </ScreenSuspense>
      );
  }
}
