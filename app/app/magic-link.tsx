import { Redirect } from 'expo-router';
import { useSession } from '@/context/auth';
import { getAuthGateStatus } from '@/lib/auth-session';

// Landing route for the `pear://magic-link?token=...` deep link.
//
// The token is verified by the AuthProvider's deep-link handler (it listens
// for inbound URLs and calls verifyMagicLink) before this screen ever renders,
// so `session` here already reflects the outcome. A <Redirect> to a screen
// whose Stack.Protected guard is currently false silently fails to navigate
// (it isn't in the mounted route table), so the target is picked off the same
// ladder app/_layout.tsx gates on — not a bare "/" or a fixed screen.
export default function MagicLinkRedirect() {
  const { session } = useSession();

  switch (getAuthGateStatus(session)) {
    case 'unauthenticated':
      return <Redirect href="/(auth)/login" />;
    case 'onboarding':
      return <Redirect href="/(onboarding)" />;
    case 'winger':
      // (winger-tabs) is a Tabs navigator with no index route, so the
      // redirect needs a concrete leaf screen — same as app/invite.tsx.
      return <Redirect href="/(winger-tabs)/activity" />;
    case 'dater':
      return <Redirect href="/(tabs)/discover" />;
  }
}
