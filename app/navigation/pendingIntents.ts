// In-memory, process-lifetime-only intents recorded while a deep link or
// onboarding flow can't yet navigate to its final destination (auth/gate not
// settled), consumed by RootNavigator's post-gate-flip effect once the target
// navigator actually mounts. No AsyncStorage needed — these only need to
// survive a single launch → auth/onboarding → gate-flip handoff.

let pendingWingerInvite: { token: string } | null = null;

export function setPendingWingerInvite(token: string): void {
  pendingWingerInvite = { token };
}

export function peekPendingWingerInvite(): { token: string } | null {
  return pendingWingerInvite;
}

export function clearPendingWingerInvite(): void {
  pendingWingerInvite = null;
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
