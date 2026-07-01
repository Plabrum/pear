import { useEffect } from 'react';
import { router } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useSession } from '@/context/auth';

export default function InviteRedirect() {
  const { session, loading } = useSession();

  useEffect(() => {
    if (loading) return;
    if (session) {
      // User is already logged in — store flag so AuthenticatedNavigator
      // handles the role-aware redirect on its next mount cycle.
      AsyncStorage.setItem('pending_invite', '1').then(() => {
        router.replace('/');
      });
    } else {
      AsyncStorage.setItem('pending_invite', '1').then(() => {
        router.replace('/(auth)/login');
      });
    }
  }, [session, loading]);

  return null;
}
