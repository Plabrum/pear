import '../global.css';
import 'react-native-url-polyfill/auto';
import 'react-native-reanimated';
import { DarkTheme, DefaultTheme, ThemeProvider } from 'expo-router/react-navigation';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import { BottomSheetModalProvider } from '@gorhom/bottom-sheet';
import { PortalHost } from '@rn-primitives/portal';
import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'react-native';
import { Toaster } from 'sonner-native';
import { QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';

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
import { getAuthGateStatus } from '@/lib/auth-session';
import { queryClient } from '@/lib/queryClient';
import { registerPushToken } from '@/lib/push';
import Splash from '@/components/ui/Splash';
import { peekPendingWingerInvite, clearPendingWingerInvite } from './invite';

export const unstable_settings = {
  anchor: '(tabs)',
};

function AppShell() {
  // Pending/offline states are handled inside AuthProvider; here the session is
  // settled — either null (unauthenticated) or a full Session.
  const { session } = useSession();
  const router = useRouter();

  // Push-token registration is a sanctioned mount/identity effect (genuine
  // external system), not a routing effect — left in place per CLAUDE.md.
  useEffect(() => {
    if (session?.user.id) registerPushToken(session.user.id);
  }, [session?.user.id]);

  // The auth ladder — single source of truth for "what does this session
  // resolve to", shared with app/magic-link.tsx's post-verify redirect so the
  // two can never disagree.
  const status = getAuthGateStatus(session);

  // One-shot winger-invite handoff. The deep link sets the in-memory intent
  // while logged out; once the user is authenticated, onboarded, and in dater
  // mode (the only state where wingpeople is reachable), consume it and jump
  // there imperatively. Deep-link handling is a sanctioned external event, and
  // an effect-time `router.replace` is mount-safe — unlike a render-time
  // <Redirect>, which raced the Stack and caused the flicker/warnings.
  useEffect(() => {
    if (status === 'dater' && peekPendingWingerInvite()) {
      clearPendingWingerInvite();
      router.replace('/(tabs)/profile/wingpeople');
    }
  }, [status, router]);

  // Declarative auth gate via Stack.Protected — mirrors the routing table in
  // CLAUDE.md (auth -> onboarding -> winger/dater). When a route's guard is
  // false it is removed and the router falls back to the first available
  // screen, so no <Redirect> and no useSegments() bookkeeping is needed. The
  // utility/deep-link routes carry no guard — always available.
  return (
    <Stack screenOptions={{ animation: 'none' }}>
      <Stack.Protected guard={status === 'unauthenticated'}>
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      </Stack.Protected>

      <Stack.Protected guard={status === 'onboarding'}>
        <Stack.Screen name="(onboarding)" options={{ headerShown: false }} />
      </Stack.Protected>

      <Stack.Protected guard={status === 'winger'}>
        <Stack.Screen name="(winger-tabs)" options={{ headerShown: false }} />
      </Stack.Protected>

      <Stack.Protected guard={status === 'dater'}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      </Stack.Protected>

      <Stack.Screen name="invite" options={{ headerShown: false }} />
      <Stack.Screen name="magic-link" options={{ headerShown: false }} />
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
              <BottomSheetModalProvider>
                <AppShell />
                {/* PortalHost sits inside the providers so portaled overlays
                    (Dialog / Sheet) inherit Query, Auth and Theme context. */}
                <PortalHost />
              </BottomSheetModalProvider>
              <Toaster position="bottom-center" richColors />
              <StatusBar barStyle={colorScheme === 'dark' ? 'light-content' : 'dark-content'} />
            </ThemeProvider>
          </AuthProvider>
        </QueryClientProvider>
      </KeyboardProvider>
    </GestureHandlerRootView>
  );
}
