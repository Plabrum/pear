import '../global.css';
import 'react-native-url-polyfill/auto';
import 'react-native-reanimated';
import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import { Stack, router, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Toaster } from 'sonner-native';
import { useQuery, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { useFonts } from 'expo-font';
import { DMSerifDisplay_400Regular } from '@expo-google-fonts/dm-serif-display';
import {
  Geist_400Regular,
  Geist_500Medium,
  Geist_600SemiBold,
  Geist_700Bold,
} from '@expo-google-fonts/geist';

import { useColorScheme } from '@/hooks/use-color-scheme';
import { AuthProvider, useSession } from '@/context/auth';
import { queryClient } from '@/lib/queryClient';
import {
  getApiProfilesMe,
  getGetApiProfilesMeQueryKey,
  getApiDatingProfilesMe,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { registerPushToken } from '@/lib/push';
import Splash from '@/components/ui/Splash';

export const unstable_settings = {
  anchor: '(tabs)',
};

function AppShell() {
  const { session, loading: authLoading } = useSession();

  const { data: profile, isPending: profilePending } = useQuery({
    queryKey: getGetApiProfilesMeQueryKey(),
    queryFn: getApiProfilesMe,
    enabled: !!session,
  });
  const { data: datingProfile, isPending: datingPending } = useQuery({
    queryKey: getGetApiDatingProfilesMeQueryKey(),
    queryFn: getApiDatingProfilesMe,
    enabled: !!session,
  });

  const loading = authLoading || (!!session && (profilePending || datingPending));
  const needsOnboarding =
    !loading &&
    !!session &&
    (!profile?.chosenName || (!datingProfile && profile?.role !== 'winger'));
  const isWinger =
    !loading &&
    !!session &&
    (profile?.role === 'winger' || datingProfile?.datingStatus === 'winging');

  useEffect(() => {
    if (session?.user.id) registerPushToken(session.user.id);
  }, [session?.user.id]);

  useEffect(() => {
    if (!session?.user.id) return;
    AsyncStorage.getItem('pending_invite').then((val) => {
      if (!val) return;
      AsyncStorage.removeItem('pending_invite');
      router.replace('/(tabs)/profile/wingpeople/' as any);
    });
  }, [session?.user.id]);

  const segments = useSegments();
  const currentGroup = segments[0];

  const targetGroup = !session
    ? '(auth)'
    : needsOnboarding
      ? '(onboarding)'
      : isWinger
        ? '(winger-tabs)'
        : '(tabs)';

  useEffect(() => {
    if (loading) return;
    if (currentGroup === targetGroup) return;
    const path =
      targetGroup === '(auth)'
        ? '/(auth)/login'
        : targetGroup === '(onboarding)'
          ? '/(onboarding)'
          : targetGroup === '(winger-tabs)'
            ? '/(winger-tabs)/friends'
            : '/(tabs)/discover';
    router.replace(path as never);
  }, [loading, currentGroup, targetGroup]);

  if (loading) return <Splash />;

  return (
    <Stack screenOptions={{ animation: 'none' }}>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="(winger-tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      <Stack.Screen name="(onboarding)" options={{ headerShown: false }} />
      <Stack.Screen name="invite" options={{ headerShown: false }} />
      <Stack.Screen name="settings" options={{ headerShown: false }} />
    </Stack>
  );
}

export default function RootLayout() {
  const colorScheme = useColorScheme();
  const [fontsLoaded] = useFonts({
    DMSerifDisplay: DMSerifDisplay_400Regular,
    Geist: Geist_400Regular,
    Geist_500Medium,
    Geist_600SemiBold,
    Geist_700Bold,
  });

  if (!fontsLoaded) return <Splash />;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <KeyboardProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
              <AppShell />
              <Toaster position="bottom-center" richColors />
              <StatusBar style="auto" />
            </ThemeProvider>
          </AuthProvider>
        </QueryClientProvider>
      </KeyboardProvider>
    </GestureHandlerRootView>
  );
}
