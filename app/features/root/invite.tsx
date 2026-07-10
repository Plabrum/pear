import { useEffect } from 'react';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useSession } from '@/context/auth';
import type { RootStackParamList } from '@/navigation/types';
import { setPendingWingerInvite } from '@/navigation/pendingIntents';

type Props = NativeStackScreenProps<RootStackParamList, 'Invite'>;

// Landing screen for the `pear://invite` deep link.
export default function InviteScreen({ navigation }: Props) {
  const { session, loading } = useSession();

  // Record the invite intent as a side effect of landing on this deep-link
  // screen unauthenticated — never during render (that would mutate module
  // state mid-render). Handling a deep link is a genuine external event, so a
  // mount/identity effect is the sanctioned place for it (see CLAUDE.md).
  useEffect(() => {
    if (!loading && !session) setPendingWingerInvite();
  }, [loading, session]);

  useEffect(() => {
    if (loading) return;
    if (session) {
      // Already authenticated — deep-link straight to wingpeople.
      navigation.navigate('DaterTabs', {
        screen: 'Profile',
        params: { screen: 'WingpeopleList' },
      });
      return;
    }
    // Not authenticated — route to login; the effect above remembers the
    // intent and RootNavigator picks it up once the session lands.
    navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
  }, [loading, session, navigation]);

  return null;
}
