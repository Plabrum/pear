import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import { updateMyProfile } from '@/lib/api/actions';

// iOS suppresses banners while the app is foregrounded unless a handler
// opts in. Without this, recipients sitting in the app on a non-chat
// screen never see the new-message push, which reads as "notifications
// arrive inconsistently."
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function registerPushToken(userId: string) {
  if (Platform.OS === 'web') return;
  if (!Device.isDevice) return;
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== 'granted') return;
  const token = (await Notifications.getDevicePushTokenAsync()).data;
  await updateMyProfile(userId, { pushToken: token });
}
