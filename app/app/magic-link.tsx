import { useEffect } from 'react';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useSession } from '@/context/auth';
import { getAuthGateStatus } from '@/lib/auth-session';
import type { RootStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<RootStackParamList, 'MagicLink'>;

// Landing screen for the `pear://magic-link?token=...` deep link.
//
// The token is verified by the AuthProvider's deep-link handler (it listens
// for inbound URLs and calls verifyMagicLink) before this screen ever renders,
// so `session` here already reflects the outcome. RootNavigator only mounts
// one of Login/Onboarding/WingerTabs/DaterTabs at a time (guarded on the same
// ladder), so resetting to a screen whose guard is currently false would fail
// — the target here is picked off the same ladder RootNavigator gates on.
export default function MagicLinkScreen({ navigation }: Props) {
  const { session } = useSession();

  useEffect(() => {
    switch (getAuthGateStatus(session)) {
      case 'unauthenticated':
        navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
        return;
      case 'onboarding':
        navigation.reset({ index: 0, routes: [{ name: 'Onboarding' }] });
        return;
      case 'winger':
        navigation.reset({
          index: 0,
          routes: [{ name: 'WingerTabs', params: { screen: 'Activity' } }],
        });
        return;
      case 'dater':
        navigation.reset({
          index: 0,
          routes: [{ name: 'DaterTabs', params: { screen: 'Discover' } }],
        });
        return;
    }
  }, [session, navigation]);

  return null;
}
