import { useEffect } from 'react';
import { NativeModules } from 'react-native';
import {
  NavigationContainer,
  useNavigationContainerRef,
  DarkTheme,
  DefaultTheme,
} from '@react-navigation/native';
import type { LinkingOptions } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { PortalHost } from '@rn-primitives/portal';

import { useColorScheme } from '@/hooks/use-color-scheme';
import { useSession } from '@/context/auth';
import { getAuthGateStatus } from '@/lib/auth-session';
import { registerPushToken } from '@/lib/push';
import type { RootStackParamList } from './types';
import {
  peekPendingWingerInvite,
  clearPendingWingerInvite,
  peekPendingOnboardingDestination,
  clearPendingOnboardingDestination,
} from './pendingIntents';
import { WingerTabsNavigator } from './WingerTabsNavigator';
import { DaterTabsNavigator } from './DaterTabsNavigator';
import LoginScreen from '../features/auth/login';
import OnboardingScreen from '../features/onboarding/index';
import InviteScreen from '../features/root/invite';
import MagicLinkScreen from '../features/root/magic-link';
import SettingsScreen from '../features/root/settings';

const RootStack = createNativeStackNavigator<RootStackParamList>();

// Only the two real deep-link entry points are URL-addressable — everything
// else is reached by in-app navigation. `Invite` carries a `?token=` query
// param the backend's `/invite/verify` redirect (and the universal-link
// fallback page) both attach — `parse` extracts it as a typed route param
// instead of a second useEffect reading it out of the raw URL.
//
// `https://usepear.app` is a real universal link (Associated Domains
// entitlement + AASA served from the backend, see project.yml and
// backend/app/platform/universal_links) — it opens the app directly when
// installed and falls back to a hosted landing page otherwise. `pear://`
// stays for the custom-scheme hops the backend's redirect routes emit.
const linking: LinkingOptions<RootStackParamList> = {
  prefixes: ['pear://', 'https://usepear.app'],
  config: {
    screens: {
      Invite: {
        path: 'invite',
        parse: {
          token: (token: string) => token,
        },
      },
      MagicLink: 'magic-link',
    },
  },
};

export function RootNavigator() {
  const colorScheme = useColorScheme();
  const { session } = useSession();
  const navigationRef = useNavigationContainerRef<RootStackParamList>();

  // Push-token registration is a sanctioned mount/identity effect (genuine
  // external system), not a routing effect.
  useEffect(() => {
    if (session?.user.id) registerPushToken(session.user.id);
  }, [session?.user.id]);

  // The auth ladder — single source of truth for "what does this session
  // resolve to", shared with app/magic-link.tsx's post-verify redirect so the
  // two can never disagree.
  const status = getAuthGateStatus(session);

  // Pending-intent handoff (winger-invite deep link, onboarding destination):
  // both are recorded while their target navigator isn't mounted yet, and
  // consumed here once `status` settles past onboarding — by then the
  // conditional <RootStack.Screen name="WingerTabs"/"DaterTabs" .../> below has
  // already rendered in the same commit, so this navigate is mount-safe (no
  // race against the query refetch that flips `status`). The invite intent
  // routes back to the always-mounted Invite screen (not straight to
  // WingpeopleList) so its token-preview confirm step still renders.
  useEffect(() => {
    if (status !== 'dater' && status !== 'winger') return;
    const pendingInvite = peekPendingWingerInvite();
    if (pendingInvite) {
      clearPendingWingerInvite();
      navigationRef.current?.navigate('Invite', { token: pendingInvite.token });
      return;
    }
    if (status !== 'dater') return;
    const dest = peekPendingOnboardingDestination();
    if (dest === 'Profile') {
      clearPendingOnboardingDestination();
      navigationRef.current?.navigate('DaterTabs', {
        screen: 'Profile',
        params: { screen: 'ProfileHome' },
      });
    } else if (dest === 'Discover') {
      clearPendingOnboardingDestination();
      navigationRef.current?.navigate('DaterTabs', { screen: 'Discover' });
    }
  }, [status, navigationRef]);

  return (
    <NavigationContainer
      ref={navigationRef}
      linking={linking}
      theme={colorScheme === 'dark' ? DarkTheme : DefaultTheme}
      onReady={() => NativeModules.PearUpdatesModule?.markBootSuccessful()}
    >
      <RootStack.Navigator screenOptions={{ headerShown: false, animation: 'none' }}>
        {status === 'unauthenticated' && <RootStack.Screen name="Login" component={LoginScreen} />}
        {status === 'onboarding' && (
          <RootStack.Screen name="Onboarding" component={OnboardingScreen} />
        )}
        {status === 'winger' && (
          <RootStack.Screen name="WingerTabs" component={WingerTabsNavigator} />
        )}
        {status === 'dater' && <RootStack.Screen name="DaterTabs" component={DaterTabsNavigator} />}

        <RootStack.Screen name="Invite" component={InviteScreen} />
        <RootStack.Screen name="MagicLink" component={MagicLinkScreen} />
        <RootStack.Screen name="Settings" component={SettingsScreen} />
      </RootStack.Navigator>
      {/* PortalHost lives inside NavigationContainer so portaled overlays
          (Dialog / Sheet) can still call useNavigation(). */}
      <PortalHost />
    </NavigationContainer>
  );
}
