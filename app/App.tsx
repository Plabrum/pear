import './global.css';
import 'react-native-url-polyfill/auto';
import 'react-native-reanimated';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import { BottomSheetModalProvider } from '@gorhom/bottom-sheet';
import { PortalHost } from '@rn-primitives/portal';
import { StatusBar } from 'react-native';
import { Toaster } from 'sonner-native';
import { QueryClientProvider } from '@tanstack/react-query';

import { useColorScheme } from '@/hooks/use-color-scheme';
import { AuthProvider } from '@/context/auth';
import { queryClient } from '@/lib/queryClient';
import { RootNavigator } from '@/navigation/RootNavigator';

export default function App() {
  const colorScheme = useColorScheme();

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <KeyboardProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BottomSheetModalProvider>
              <RootNavigator />
              {/* PortalHost sits inside the providers so portaled overlays
                  (Dialog / Sheet) inherit Query and Auth context. */}
              <PortalHost />
            </BottomSheetModalProvider>
            <Toaster position="bottom-center" richColors />
            <StatusBar barStyle={colorScheme === 'dark' ? 'light-content' : 'dark-content'} />
          </AuthProvider>
        </QueryClientProvider>
      </KeyboardProvider>
    </GestureHandlerRootView>
  );
}
