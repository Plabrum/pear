import { NativeModules, Platform } from 'react-native';
import { updateMyProfile } from '@/lib/api/actions';

// Foreground presentation is handled natively in AppDelegate's
// UNUserNotificationCenterDelegate — iOS suppresses banners while the app is
// foregrounded unless a delegate opts in, so that lives next to the rest of
// the push registration in PearNotificationsModule/AppDelegate.swift.
const { PearNotificationsModule } = NativeModules;

export async function registerPushToken(userId: string) {
  if (Platform.OS !== 'ios') return;
  const isDevice: boolean = await PearNotificationsModule.isDevice();
  if (!isDevice) return;
  const token: string | null = await PearNotificationsModule.requestAndRegister();
  if (!token) return;
  await updateMyProfile(userId, { pushToken: token });
}
