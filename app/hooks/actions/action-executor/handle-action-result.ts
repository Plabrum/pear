import { Linking } from 'react-native';
import type { useRouter } from 'expo-router';
import { toast } from 'sonner-native';

import type { ActionExecutionResponse } from '@/lib/actions/types';

type Router = ReturnType<typeof useRouter>;

/**
 * Honour the backend's `action_result` follow-up. Clipboard results show a toast
 * hint instead of copying directly since expo-clipboard isn't a dependency yet.
 */
export function handleActionResult(response: ActionExecutionResponse, router: Router): void {
  const result = response.action_result;
  if (!result) return;

  switch (result.type) {
    case 'redirect':
      if (result.path === '..') router.back();
      else router.push(result.path as never);
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
