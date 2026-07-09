import { useEffect } from 'react';
import {
  NavigationContainer,
  useNavigationContainerRef,
  DarkTheme,
  DefaultTheme,
} from '@react-navigation/native';
import type { LinkingOptions } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

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
import LoginScreen from '../app/(auth)/login';
import OnboardingScreen from '../app/(onboarding)/index';
import InviteScreen from '../app/invite';
import MagicLinkScreen from '../app/magic-link';
import SettingsScreen from '../app/settings';

const RootStack = createNativeStackNavigator<RootStackParamList>();

// Only the two real deep-link entry points are URL-addressable — everything
// else is reached by in-app navigation, same as before (scheme `pear` only,
// no universal links).
const linking: LinkingOptions<RootStackParamList> = {
  prefixes: ['pear://'],
  config: {
    screens: {
      Invite: 'invite',
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
  // consumed here once `status` flips to 'dater' — by then the conditional
  // <RootStack.Screen name="DaterTabs" .../> below has already rendered in
  // the same commit, so this navigate is mount-safe (no race against the
  // query refetch that flips `status`).
  useEffect(() => {
    if (status !== 'dater') return;
    if (peekPendingWingerInvite()) {
      clearPendingWingerInvite();
      navigationRef.current?.navigate('DaterTabs', {
        screen: 'Profile',
        params: { screen: 'WingpeopleList' },
      });
      return;
    }
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
    </NavigationContainer>
  );
}
