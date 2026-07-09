import { Linking } from 'react-native';
import { toast } from 'sonner-native';

import type { ActionExecutionResponse } from '@/lib/actions/types';

// Only `goBack` is ever used here — scoped to that rather than the full
// NavigationProp shape to sidestep React Navigation v7's getState() typing
// mismatch between the hook's return type and the standalone NavigationProp type.
type Navigation = { goBack: () => void };

/**
 * Honour the backend's `action_result` follow-up. Clipboard results show a toast
 * hint instead of copying directly since expo-clipboard isn't a dependency yet.
 *
 * No backend action currently constructs a `redirect` result other than the
 * `'..'` (go back) convention — `result.path` is a free-form string the
 * backend could in principle send for a screen this client doesn't know
 * about, so anything else is a no-op (logged) rather than a crash.
 */
export function handleActionResult(
  response: ActionExecutionResponse,
  navigation: Navigation
): void {
  const result = response.action_result;
  if (!result) return;

  switch (result.type) {
    case 'redirect':
      if (result.path === '..') {
        navigation.goBack();
      } else {
        console.warn(`handleActionResult: unhandled redirect path "${result.path}"`);
      }
      return;
    case 'download_file':
      void Linking.openURL(result.url);
      return;
    case 'copy_to_clipboard':
      if (result.toast) toast.success(result.toast);
      return;
    default:
      return;
  }
}
