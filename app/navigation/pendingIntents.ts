// In-memory, process-lifetime-only intents recorded while a deep link or
// onboarding flow can't yet navigate to its final destination (auth/gate not
// settled), consumed by RootNavigator's post-gate-flip effect once the target
// navigator actually mounts. No AsyncStorage needed — these only need to
// survive a single launch → auth/onboarding → gate-flip handoff.

let pendingWingerInvite = false;

export function setPendingWingerInvite(): void {
  pendingWingerInvite = true;
}

export function peekPendingWingerInvite(): boolean {
  return pendingWingerInvite;
}

export function clearPendingWingerInvite(): void {
  pendingWingerInvite = false;
}

type OnboardingDestination = 'Profile' | 'Discover';

let pendingOnboardingDestination: OnboardingDestination | null = null;

export function setPendingOnboardingDestination(dest: OnboardingDestination): void {
  pendingOnboardingDestination = dest;
}

export function peekPendingOnboardingDestination(): OnboardingDestination | null {
  return pendingOnboardingDestination;
}

export function clearPendingOnboardingDestination(): void {
  pendingOnboardingDestination = null;
}
