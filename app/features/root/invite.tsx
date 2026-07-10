import { useEffect, useState } from 'react';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { toast } from 'sonner-native';

import { useSession } from '@/context/auth';
import { getAuthGateStatus } from '@/lib/auth-session';
import { acceptInviteByToken } from '@/lib/api/actions';
import { inviteVerifyInviteVerify } from '@/lib/api/generated/contacts/contacts';
import type { InviteVerifyOut } from '@/lib/api/generated/model';
import { Button } from '@/components/Button';
import { LargeNavHeader } from '@/components/LargeNavHeader';
import { View, Text } from '@/lib/tw';
import type { RootStackParamList } from '@/navigation/types';
import { setPendingWingerInvite } from '@/navigation/pendingIntents';

type Props = NativeStackScreenProps<RootStackParamList, 'Invite'>;

type PreviewState =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'ready'; preview: InviteVerifyOut };

// Landing screen for the `pear://invite` / `https://usepear.app/invite` link.
export default function InviteScreen({ navigation, route }: Props) {
  const { session, loading } = useSession();
  const token = route.params?.token;
  const [preview, setPreview] = useState<PreviewState>({ kind: 'loading' });
  const [accepting, setAccepting] = useState(false);

  // Deep-link handoff while unauthenticated: record the intent, then route to
  // Login — RootNavigator's pending-intent effect resumes it once a session
  // lands. A genuine external event (arriving via a link before the session
  // resolves), so a mount effect is the sanctioned place for it.
  useEffect(() => {
    if (loading || session) return;
    if (token) setPendingWingerInvite(token);
    navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
  }, [loading, session, token, navigation]);

  // Preview the token's target dater once authenticated — another deep-link
  // driven one-time fetch, not a value derivable from render.
  useEffect(() => {
    if (loading || !session || !token) return;
    let cancelled = false;
    inviteVerifyInviteVerify({ token })
      .then((result) => {
        if (!cancelled) setPreview({ kind: 'ready', preview: result });
      })
      .catch(() => {
        if (!cancelled) setPreview({ kind: 'error' });
      });
    return () => {
      cancelled = true;
    };
  }, [loading, session, token]);

  if (loading || !session || !token) return null;

  const goToHome = () => {
    const status = getAuthGateStatus(session);
    if (status === 'winger') {
      navigation.navigate('WingerTabs', { screen: 'Friends', params: { screen: 'FriendsList' } });
    } else {
      navigation.navigate('DaterTabs', { screen: 'Discover' });
    }
  };

  const handleAccept = async () => {
    setAccepting(true);
    const result = await acceptInviteByToken(token).catch((err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'Could not accept invite');
      return undefined;
    });
    setAccepting(false);
    if (!result) return;
    const status = getAuthGateStatus(session);
    if (status === 'winger') {
      navigation.navigate('WingerTabs', { screen: 'Friends', params: { screen: 'FriendsList' } });
    } else {
      navigation.navigate('DaterTabs', {
        screen: 'Profile',
        params: { screen: 'WingpeopleList' },
      });
    }
  };

  return (
    <View className="flex-1 bg-background">
      <LargeNavHeader back={false} onBack={goToHome} title="Wingperson Invite" />
      <View className="flex-1 items-center justify-center gap-24 px-24">
        {preview.kind === 'loading' && <Text className="text-fg-muted">Loading invite…</Text>}
        {preview.kind === 'error' && (
          <>
            <Text className="text-fg text-center text-16">
              This invite link is invalid or has expired.
            </Text>
            <Button variant="secondary" onPress={goToHome}>
              Done
            </Button>
          </>
        )}
        {preview.kind === 'ready' && preview.preview.alreadyLinked && (
          <>
            <Text className="text-fg text-center text-16">
              This invite has already been accepted.
            </Text>
            <Button variant="secondary" onPress={goToHome}>
              Done
            </Button>
          </>
        )}
        {preview.kind === 'ready' && !preview.preview.alreadyLinked && (
          <>
            <Text className="text-fg text-center text-18">
              Accept invite from {preview.preview.daterName ?? 'a Pear dater'} to be their
              wingperson?
            </Text>
            <View className="flex-row gap-12">
              <Button variant="secondary" onPress={goToHome}>
                Decline
              </Button>
              <Button variant="primary" loading={accepting} onPress={handleAccept}>
                Accept
              </Button>
            </View>
          </>
        )}
      </View>
    </View>
  );
}
